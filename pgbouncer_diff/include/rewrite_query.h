//
// Created by mehmet on 22.01.2019.
//

#ifndef PGBOUNCER_RUBY_REWRITE_QUERY_H
#define PGBOUNCER_RUBY_REWRITE_QUERY_H
bool rewrite_query(PgSocket *client, PktHdr *pkt);


void printHex(void *buffer, const unsigned int n) ;
#endif //PGBOUNCER_RUBY_REWRITE_QUERY_H
