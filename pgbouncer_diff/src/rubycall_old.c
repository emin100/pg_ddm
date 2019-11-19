/*
Copyright 2015-2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Licensed under the Amazon Software License (the "License").
You may not use this file except in compliance with the License. A copy of the License is located at

    http://aws.amazon.com/asl/

or in the "license" file accompanying this file.
This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and limitations under the License.
*/

/*
 * pgbouncer-rr extension: call external python function
 */

#include <ruby.h>
#include "bouncer.h"
#include <usual/pgutil.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

PgSocket *clientx;
int loader = 0;

char* concat(const char *s1, const char *s2)
{
    char *result = malloc(strlen(s1) + strlen(s2) + 1); // +1 for the null-terminator
    // in real code you would check for errors in malloc here
    strcpy(result, s1);
    strcat(result, s2);
    return result;
}


void load(char *module)
{
    rb_require(module);
}

char *embeded(char *query_str)
{
    char *res;
    int state;
    int state2;
    VALUE result;
    VALUE parser;

    rb_require("./mask_ruby/parser.rb");
    slog_error(clientx, "Geldia");

    ID class_id = rb_intern("PgQueryOpt");
    VALUE class = rb_const_get(rb_cObject, class_id);
    VALUE obj = rb_class_new_instance(Qnil, Qnil, class);
    slog_error(clientx, "Geldib");
//    parser = rb_funcall(rb_str_new2("PgQueryOpt"), rb_intern("new"), 0);
//    slog_error(clientx, "Geldib");
//    rb_funcall(parser, rb_intern("set_sql"),1, query_str);
//    slog_error(clientx, "Geldic");

//    VALUE obj = rb_define_class("PgQueryOpt", rb_cObject);
//    parser =  rb_funcall(obj, rb_intern("new"), 0);
//    slog_error(clientx, "Geldib");
//    rb_funcall(parser, rb_intern("set_sql"),1, query_str);
////    VALUE exception = rb_errinfo();
////    slog_error(clientx, "Geldie %s%"PRIsVALUE"",rb_funcall(exception, rb_intern("full_message"), 0));
//
//    slog_error(clientx, "Geldic");
//    result = rb_funcall(parser, rb_intern("get_sql"), 0);
//
//    slog_error(clientx, "Geldid");
//    res = StringValueCStr(result);
//    slog_error(clientx, "SQL_CHANGED %s",res);
    return query_str;


//    rb_eval_string_protect(concat(concat("$object = PgQuery.parse(\"",query_str),"\")"),&state);
//    if(state) {
//        VALUE exception = rb_errinfo();
//        slog_error(clientx, "Geldie %s%"PRIsVALUE"",rb_funcall(exception, rb_intern("full_message"), 0));
//        return query_str;
//    }else{
//        rb_eval_string_wrap("$result = $object.get_sql",&state2);
//        if(state2) {
//            slog_error(clientx, "Geldic");
//            return query_str;
//        } else {
//            result = rb_gv_get("$result");
//            if (TYPE(result) == T_STRING) {
//                res = StringValueCStr(result);
//                slog_error(clientx, "SQL_CHANGED %s",res);
//                return res;
//
//            } else {
//                slog_error(clientx, "Geldid");
//                return query_str;
//            }
//        }
//
//    }

}


//char *call(char *query_str) {
char *rubycall(PgSocket *client, char *username, char *query_str) {
    clientx = client;
    slog_error(clientx, "21");

    char *res = NULL;
    int state;
    if(loader == 0 ){
        RUBY_INIT_STACK;
        ruby_init();

        ruby_init_loadpath();
        ruby_script("RewriteQuery");
        slog_error(client, "1");
        rb_define_module("Gem");
        rb_require("rubygems");
        loader = 1;
    }


    slog_error(clientx, "2");

    rb_require("./mask_ruby/parser.rb");
    slog_error(clientx, "Geldia");



    VALUE myclass = rb_const_get(rb_cObject, rb_intern("PgQueryOpt"));
    slog_error(clientx, "Geldib");

    VALUE xx = rb_funcall(myclass, rb_intern("new"), 0);
    rb_ivar_set(xx, rb_intern("@sql"), rb_str_new_cstr(query_str));
    VALUE iv;

    iv = rb_iv_get(xx, "@sql");
    
    VALUE zz = rb_funcall(xx, rb_intern("get_sql"), 0);

    if (TYPE(zz) == T_STRING) {
        res = StringValueCStr(zz);
        slog_error(clientx, "SQL_CHANGEDx %s",res);
        return res;

    }


//    rb_funcall(myclass, rb_intern("set_sql"), 1, rb_str_new_cstr(query_str));
//    rb_funcall(myclass, rb_intern("test"), 0);
    slog_error(clientx, "Geldic");



//    ID class_id = rb_intern("PgQueryOpt");
//    VALUE class = rb_const_get(rb_cObject, class_id);
//    VALUE pass;
//    VALUE obj = rb_class_new_instance(0, pass, class);
////    rb_cv_get(obj,"@sql");
////    VALUE xx = rb_funcall(obj, rb_intern("new"),0);
//    slog_error(clientx, "Geldib");
//    rb_funcall(, rb_intern("PgQueryOpt.new"),0);
////    rb_ivar_set(obj, rb_intern("@sql"), rb_str_new2(query_str));
////
////    slog_error(clientx, "Gel %s",StringValueCStr(rb_ivar_get(obj, rb_intern("@sql"))));
//    rb_funcall(obj, rb_intern("get_sql"),0);
//    slog_error(clientx, "Geldic");

    return NULL;



//    res = rb_protect(embeded, query_str , &state);
//
//    slog_error(clientx, "3");
//    if (state)
//    {
//        slog_error(clientx, "4");
//        return NULL;
//    }else {
//        slog_error(clientx, "5");
//
//        slog_error(clientx, "6");
//        slog_error(clientx, "SQL_ORIG %s",query_str);
//        slog_error(clientx, "SQL %s",res);
//
//        slog_error(clientx, "7");
//        return res;
//    }
}
//
//char *rubycallx(PgSocket *client, char *username, char *query_str) {
//
//    clientx = client;
//    VALUE result;
//
//    RUBY_INIT_STACK;
//    ruby_init();
//
//    ruby_init_loadpath();
//    ruby_script("RewriteQuery");
//    slog_error(client, "1");
//    rb_define_module("Gem");
//    rb_require("rubygems");
//
////    result = rb_thread_create(call, query_str);
//
//	return NULL;
//}