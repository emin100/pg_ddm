/*
 Copyright 2015-2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.

 Licensed under the Amazon Software License (the "License").
 You may not use this file except in compliance with the License. A copy of the License is located at

 http://aws.amazon.com/asl/

 or in the "license" file accompanying this file.
 This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and limitations under the License.
 */

/*
 * Some peace of codes owner is pgbouncer-rr extension.
 * See in https://github.com/awslabs/pgbouncer-rr-patch
 */

#include "bouncer.h"
#include <usual/pgutil.h>

/* private function prototypes */
void printHex(void *buffer, const unsigned int n);
char* strip_newlines(char *s);
bool handle_incomplete_packet(PgSocket *client, PktHdr *pkt);
bool handle_failure(PgSocket *client);
char* tag_rewritten(char *query);
bool is_rewritten(char *query);

/* rewrite_query:
 * applied to packets of type 'Q' (Query) and 'P' (Prepare) only
 */
bool rewrite_query(PgSocket *client, PktHdr *pkt) {
	SBuf *sbuf = &client->sbuf;
	char *pkt_start;
	char *stmt_str = "", *query_str, *loggable_query_str, *tmp_new_query_str,
			*tmp_new_query_role = "master", *new_query_str;
	struct query_return qr;
	char *new_io_buf;
	char *remaining_buffer_ptr;
	int new_pkt_len, remaining_buffer_len;
	int i;
	PgDatabase *db;
	PgPool *pool;


	qr.query = NULL;

	if (!handle_incomplete_packet(client, pkt))
		return false;

	/* extract query string from packet */
	/* first byte is the packet type (which we already know)
	 * next 4 bytes is the packet length
	 * For packet type 'Q', the query string is next
	 * 	'Q' | int32 len | str query
	 * For packet type 'P', the query string is after the stmt string
	 * 	'P' | int32 len | str stmt | str query | int16 numparams | int32 paramoid
	 * (Ref: https://www.pgcon.org/2014/schedule/attachments/330_postgres-for-the-wire.pdf)
	 */
	pkt_start = (char*) &sbuf->io->buf[sbuf->io->parse_pos];
	if (pkt->type == 'Q') {
		query_str = (char*) pkt_start + 5;
	} else if (pkt->type == 'P') {
		stmt_str = pkt_start + 5;
		query_str = stmt_str + strlen(stmt_str) + 1;
	} else {
		fatal("Invalid packet type - expected Q or P, got %c", pkt->type);
	}

	loggable_query_str = strip_newlines(query_str);
	slog_debug(client, "rewrite_query: Username => %s",
			client->login_user->name);
	slog_debug(client, "rewrite_query: Orig Query=> %s", loggable_query_str);
	free(loggable_query_str);

	/* don't process same query again */
	if (is_rewritten(query_str))
		return true;

	if (cf_pg_ddm_enabled) {
        /* call ruby function to rewrite the query */
        qr = rubycall(client, client->login_user->name, query_str);
        tmp_new_query_str = qr.query;
    }else {
        tmp_new_query_str = query_str;
    }
    if (tmp_new_query_str == NULL) {
        slog_debug(client, "query unchanged");
        return true;
    }
    new_query_str = tag_rewritten(tmp_new_query_str);
    slog_debug(client, "query tag changed %s", new_query_str);
//    free(tmp_new_query_str);
    loggable_query_str = strip_newlines(new_query_str);
    slog_debug(client, "rewrite_query: New => %s", loggable_query_str);
    free(loggable_query_str);

    /* new query must fit in the buffer */
    if ((int) (sbuf->io->recv_pos + strlen(new_query_str)
            - strlen(query_str)) > (int) cf_sbuf_len) {
        slog_error(client,
                "Rewritten query will not fit into the allocated buffer!");
        free(new_query_str);
        return handle_failure(client);
    }

    /* manipulate the buffer to replace query */
    /* clone buffer */
    new_io_buf = malloc(cf_sbuf_len);
    if (new_io_buf == NULL) {
        fatal_perror("malloc");
    }
    memcpy(new_io_buf, sbuf->io->buf, cf_sbuf_len);
    i = sbuf->io->parse_pos;
    /* packet type */
    new_io_buf[i++] = pkt->type;
    /* packet length */
    new_pkt_len = pkt->len + strlen(new_query_str) - strlen(query_str) - 1;
    new_io_buf[i++] = (new_pkt_len >> 24) & 255;
    new_io_buf[i++] = (new_pkt_len >> 16) & 255;
    new_io_buf[i++] = (new_pkt_len >> 8) & 255;
    new_io_buf[i++] = new_pkt_len & 255;
    /* statement str - for type P */
    if (pkt->type == 'P') {
        strcpy(&new_io_buf[i], stmt_str);
        i += strlen(stmt_str) + 1;
    }
    /* query string */
    strcpy(&new_io_buf[i], new_query_str);
    i += strlen(new_query_str) + 1;
    /* copy everything else in buffer */
    remaining_buffer_ptr = query_str + strlen(query_str) + 1;
    remaining_buffer_len = (char*) &sbuf->io->buf[sbuf->io->recv_pos]
            - remaining_buffer_ptr;
    memcpy(&new_io_buf[i], remaining_buffer_ptr, remaining_buffer_len);
    i += remaining_buffer_len;
    /* replace original buffer with new buffer */
    memcpy(sbuf->io->buf, new_io_buf, i);
    /* adjust buffer recv_pos index to new position */
    sbuf->io->recv_pos = i;
    /* update PktHdr structure */
    pkt->len = new_pkt_len + 1;
    iobuf_parse_all(sbuf->io, &pkt->data);

    free(new_query_str);
    free(new_io_buf);


	if (cf_pg_ddm_rewrite_route) {
		if (qr.query == NULL) {
			qr = rubycall_role(client, client->login_user->name, query_str);
		}
        slog_debug(client, "DB Role: %s", qr.role);
		tmp_new_query_role = qr.role;
	}

	if (cf_pg_ddm_ini_route || cf_pg_ddm_rewrite_route) {
		if (client->query_start == client->xact_start) {

			if (client->pool->db->route == 1) {
				db = find_routing_database(client->pool->db->name,
						tmp_new_query_role, 0);
				if (db == NULL) {
					slog_error(client,
							"check ini and/or routing rules function");
				} else {
					pool = get_pool(db, client->login_user);
					if (client->pool != pool) {
						if (client->link != NULL) {
							slog_debug(client,
									"releasing existing server connection");
							release_server(client->link);
							client->link = NULL;
						}
						slog_debug(client,
								"assigning client to connection pool for database <%s>",
								db->name);
						client->pool = pool;
					} else {
						slog_debug(client, "already connected to pool <%s>",
								db->name);
					}
				}
			}
		} else {
			slog_debug(client, "use old connection info <%s>",
					client->pool->db->name);
		}
	}
	return true;
}

/* handle incomplete packet in the buffer
 *  - if buffer is too small, then either
 *     - continue without rewrite (if rewrite_query_disconnect_on_failure = false)
 *     - disconnect client (if rewrite_query_disconnect_on_failure = true)
 *  - if buffer is not too small, return false and allow main loop to wait for rest of packet
 */
bool handle_incomplete_packet(PgSocket *client, PktHdr *pkt) {
	if (incomplete_pkt(pkt)) {
		slog_warning(client,
				"Unable to rewrite query - buffer does not contain full query packet");
		slog_warning(client, "Buffer len -> %d, Pkt len -> %d",
				mbuf_written(&pkt->data), pkt->len);
		/* is packet size bigger than the buffer size? */
		if ((int) pkt->len > (int) cf_sbuf_len) {
			/* Nope - we will never get the full packet */
			slog_error(client,
					"Packet length (%d) bigger than buffer size (%d)", pkt->len,
					cf_sbuf_len);
			slog_error(client,
					"Increase buffer size in config (pkt_buf) to contain the maximum sized query");
			return handle_failure(client);
		} else {
			/* there is room in the buffer - let's wait for rest of packet */
			slog_warning(client, "Wait for rest of packet to arrive");
			return false;
		}
	}
	return true;
}

/*
 * Handle rewrite failure
 * Either continue with original query,
 * or disconnect client
 * based on rewrite_query_disconnect_on_failure setting
 */
bool handle_failure(PgSocket *client) {
	slog_error(client, "Preserving original query");
	return true;
}

/* copy query string with no newlines, so that it will print correctly in slog_ functions
 */
char* strip_newlines(char *s) {
	char *n;
	char *p1;
	n = strdup(s);
	if (n == NULL) {
		fatal_perror("strdup");
	}
	for (p1 = n; *p1; p1++) {
		if (*p1 == '\n') {
			*p1 = ' ';
		}
	}
	return n;
}

/* query tagging to prevent multiple rewrite */
char* tag_rewritten(char *query) {
	char *tag = malloc(64);
	char *taggedQuery;
	if (tag == NULL) {
		fatal_perror("malloc");
	}
	sprintf(tag, "/* rewritten: pid=%05d */", getpid());
	taggedQuery = malloc(strlen(tag) + strlen(query) + 1);
	if (taggedQuery == NULL) {
		fatal_perror("malloc");
	}
	sprintf(taggedQuery, "%s%s", query, tag);
	free(tag);
	return taggedQuery;
}
bool is_rewritten(char *query) {
	bool is_tagged = false;
	char *tag = malloc(64);
	if (tag == NULL) {
		fatal_perror("malloc");
	}
	sprintf(tag, "/* rewritten: pid=%05d */", getpid());
//    put conf file exception tag
	if (strstr(query, tag) || strstr(query, "/* rewritten: pid=-99 */")) {
		is_tagged = true;
	}
	free(tag);
	return is_tagged;
}

/* Packet dump for debugging */
void printHex(void *buffer, const unsigned int n) {
	char *data = (char*) buffer;
	unsigned int i = 0;
	char line[17] = { };
	printf("%.8lX | ", (uintptr_t) data);
	while (i < n) {
		line[i % 16] = *(data + i);
		if ((line[i % 16] < 32) || (line[i % 16] > 126)) {
			line[i % 16] = '.';
		}
		printf("%.2X", (unsigned char) *(data + i));
		i++;
		if (i % 4 == 0) {
			if (i % 16 == 0) {
				if (i < n - 1)
					printf(" | %s\n%.8lX | ", (char*) &line,
							(uintptr_t) data + i);
			} else {
				printf(" ");
			}
		}
	}
	while (i % 16 > 0) {
		(i % 4 == 0) ? printf("   ") : printf("  ");
		line[i % 16] = ' ';
		i++;
	}
	printf(" | %s\n", (char*) &line);
}
