
#include <ruby.h>
#include "bouncer.h"

int loader = 0;


struct query_data {
  VALUE query_str;
  VALUE username;
  VALUE db;
  VALUE etcd_host;
  VALUE etcd_port;
  VALUE etcd_user;
  VALUE etcd_passwd;
  VALUE user_regex;
  VALUE tag_regex;
};


VALUE *embeded(VALUE q)
{
    VALUE result;
    VALUE parser;

    struct query_data* data = (struct query_data*) q;

    parser = rb_const_get(rb_cObject, rb_intern("PgQueryOpt"));

    VALUE xx = rb_funcall(parser, rb_intern("new"), 0);
    rb_funcall(xx, rb_intern("set_prop"), 9, data->query_str, data->username, data->db, data->etcd_host, data->etcd_port, data->etcd_user, data->etcd_passwd, data->user_regex, data->tag_regex);
    result = rb_funcall(xx, rb_intern("get_sql"), 0);


    return result;

}


char *rubycall(PgSocket *client, char *username, char *query_str) {

    VALUE *res;
    int state;

    if(loader == 0 ){
        RUBY_INIT_STACK;
        ruby_init();
        ruby_init_loadpath();
        ruby_script("RewriteQuery");
        rb_define_module("Gem");
        rb_require("rubygems");
        rb_require("/etc/pg_ddm/mask_ruby/parser.rb");
        loader = 1;
    }

    struct query_data q;
    q.query_str = rb_str_new_cstr(query_str);
    q.username = rb_str_new_cstr(username);
    q.db = rb_str_new_cstr(client->db->name);
    q.etcd_host = rb_str_new_cstr(cf_etcd_host);
    q.etcd_port = rb_str_new_cstr(cf_etcd_port);
    q.etcd_user = rb_str_new_cstr(cf_etcd_user);
    q.etcd_passwd = rb_str_new_cstr(cf_etcd_passwd);
    q.user_regex = rb_str_new_cstr(cf_user_regex);
    q.tag_regex = rb_str_new_cstr(cf_tag_regex);


    res = rb_protect(embeded, (VALUE)(&q), &state);

    if (state)
    {
        slog_error(client,"Error when executed ruby code");
        ruby_cleanup(state);
        return NULL;
    }else {
        if (TYPE(res) == T_STRING) {
            return  StringValueCStr(res);
        }
    }

}