//
// Created by mehmet on 22.01.2019.
//

#ifndef PGBOUNCER_RUBY_RUBYCALL_H
#define PGBOUNCER_RUBY_RUBYCALL_H

struct query_return {
    char *query;
    char *role;
};

struct query_return rubycall(PgSocket *client, char *username, char *query_str) ;
struct query_return rubycall_role(PgSocket *client, char *username, char *query_str) ;


#endif //PGBOUNCER_RUBY_RUBYCALL_H
