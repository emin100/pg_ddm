import configparser
from urllib.parse import urlparse, urljoin

import flask
import forms
import psycopg2
from etcd import Etcd
from flask import Flask, render_template, redirect, url_for, session, flash, Response, json, request, g
from flask_babel import Babel, _
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, logout_user, login_required, login_user
from models import User
import uuid

babel = Babel()
login_manager = LoginManager()
config_filepath = '/etc/pg_ddm/pg_ddm.ini'

config = configparser.RawConfigParser(allow_no_value=True)
config.read(config_filepath)


def create_app():
    app_obj = Flask(__name__)

    Bootstrap(app_obj)
    babel.init_app(app_obj)
    login_manager.init_app(app_obj)

    app_obj.config['BOOTSTRAP_SERVE_LOCAL'] = True
    app_obj.config['BABEL_DEFAULT_LOCALE'] = 'en'
    app_obj.config['SECRET_KEY'] = 'Test'
    app_obj.config['WTF_I18N_ENABLED'] = True
    app_obj.config['WTF_CSRF_SECRET_KEY'] = 'a random string'
    app_obj.config['WTF_CSRF_ENABLED'] = True

    login_manager.login_view = "login"
    login_manager.session_protection = "strong"

    return app_obj


app = create_app()


@babel.localeselector
def get_locale():
    # if a user is logged in, use the locale from the user settings
    user_obj = getattr(g, 'user', None)
    if user_obj is not None:
        return user_obj.locale
    # otherwise try to guess the language from the user accept
    # header the browser transmits.  We support de/fr/en in this
    # example.  The best match wins.
    return request.accept_languages.best_match(['en'])


#
#
# @babel.timezoneselector
# def get_timezone():
#     user = getattr(g, 'user', None)
#     if user is not None:
#         return user.timezone


def pagination(total):
    page = 1
    row_in_page = 20
    total_page = int(total / row_in_page) + 1

    if request.args.get('page') is not None:
        page = int(request.args.get('page'))
    start = page - 5
    diff = 0
    if page < 6:
        start = 1
        diff = page - 5

    end = page + 6 - diff
    if page + 6 > total_page:
        end = total_page + 1 - diff
    if end - start < 10:
        start = start - (11 - (end - start))
    if start < 0:
        start = 1
    if end > total_page:
        end = total_page
    # print({'total': total, 'page': page, 'total_page': total_page, 'row_in_page': row_in_page, 'start': start,
    #                   'end': end})
    return {'total': total, 'page': page, 'total_page': total_page, 'row_in_page': row_in_page, 'start': start,
            'end': end}


@app.route('/')
@login_required
def index():
    return render_template('dashboard.html', user='mehmet')


@app.route('/logout')
@login_required
def logout():
    flash(_('Bye Bye'), 'danger')
    logout_user()
    return redirect(url_for('index'))


# @login_manager.unauthorized_handler
# def unauthorized():
#     # do stuff
#     return redirect(url_for('login'))


@login_manager.user_loader
def load_user(user_id):
    loaded_user = User(user_id)
    g.user = loaded_user

    return loaded_user


def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = forms.LoginForm()
    if form.validate_on_submit():
        login_user_obj = User(form.username.data, form.password.data)
        if login_user_obj.verify_password():
            login_user(login_user_obj, remember=form.remember_me.data)
            session['logged_in'] = True
            g.user = login_user_obj

            flask.flash(_('Logged in successfully.'))

            next_url = flask.request.args.get('next')
            # is_safe_url should check if the url is safe for redirects.
            # See http://flask.pocoo.org/snippets/62/ for an example.
            if not is_safe_url(next_url):
                return flask.abort(400)

            return flask.redirect(next_url or flask.url_for('index'))
        flash(_('Login Failed!'), 'danger')
    return flask.render_template('login.html', form=form)


@app.route('/tables', methods=['GET', 'POST'])
@app.route('/tables/<url_type>', methods=['GET', 'POST'])
@login_required
def tables(url_type=None):
    etcd_conn = Etcd()

    config.read(config_filepath)
    db_list = []
    for db in config['databases']:
        db_list.append((db, db))

    button_list = [{'name': _('Update'), 'href': '/tables/change'}, {'name': _('List'), 'href': '/tables'}]

    if url_type == 'change':
        form = forms.TablesForm()
        form.db.choices = db_list
        if form.validate_on_submit():
            conn = None
            try:
                db = config['databases'][form.db.data]
                conn = psycopg2.connect(db, user=form.username.data, password=form.password.data)
                cur = conn.cursor()
                cur.execute("""SELECT i.table_catalog,i.table_schema,i.table_name,(
                                 SELECT array_to_json(array_agg(col_array)) FROM (
                                     SELECT i2.column_name,i2.data_type 
                                     FROM information_schema.columns i2
                                     WHERE i2.table_catalog = i.table_catalog 
                                     AND i2.table_schema = i.table_schema 
                                     AND i2.table_name = i.table_name
                    
                                 ) col_array
                                ) FROM information_schema.columns i
                                 WHERE i.table_schema NOT IN ('pg_catalog','information_schema','mask')
                                 GROUP BY 1,2,3""")

                for row in cur.fetchall():
                    key = '/{}/{}/{}'.format(str(form.db.data), str(row[1]), str(row[2]))
                    print(key)
                    etcd_conn.put(key, json.dumps(row[3]))
                cur.close()
            except (Exception, psycopg2.DatabaseError) as error:
                flash(_('DB Error'), 'error')
            finally:
                if conn is not None:
                    conn.close()

            flash(_('Tables') + ' ' + _('Updated'), 'info')
            return flask.redirect(flask.url_for('tables'))

        return flask.render_template('list.html', main_header=_('Tables'), form=form, button_list=button_list)
    else:
        form_db = forms.TableSelectForm()
        form_db.db.choices = db_list
        if form_db.validate_on_submit():
            group_list = etcd_conn.search('/{}/'.format(str(form_db.db.data)), json_field=False)
            headers = [_('Name'), _('Group Name')]
            links = [{'name': _('Update'), 'type': 'danger', 'link': '/tables/update'}]
            page = pagination(len(group_list))

            return flask.render_template('list.html', main_header=_('Tables'),
                                         list=group_list[(int(page.get('page')) - 1) * int(
                                             page.get('row_in_page')):((int(page.get('page')) - 1) * int(
                                             page.get('row_in_page'))) + int(page.get('row_in_page'))],
                                         headers=headers,
                                         links=links, button_list=button_list, pagination=page)
        return flask.render_template('list.html', main_header=_('Tables'), form=form_db, button_list=button_list)


@app.route('/rules', methods=['GET', 'POST'])
@app.route('/rules/<url_type>', methods=['GET', 'POST'])
@login_required
def rules(url_type=None):
    etcd_conn = Etcd()
    button_list = [{'name': _('New'), 'href': '/rules/change'}, {'name': _('List'), 'href': '/rules'}]
    if url_type == 'change':
        form = forms.RulesForm()
        if form.validate_on_submit():
            status = 'false'
            if form.enabled.data is True:
                status = 'true'
            prop = ''
            if form.rule.data in form.test.keys():
                if len(form.test[form.rule.data]) > 0:
                    prop = "["
                    for i in form.test[form.rule.data]:
                        x = str(i).replace('open_close_', '')
                        if x == 'col':
                            prop += '%col%,'
                        elif str(flask.request.form[x]).isdigit():
                            prop += '{"A_Const": {"val": ' + flask.request.form[x] + '}},'
                        else:
                            prop += '{"A_Const": {"val": {"String": {"str": "' + flask.request.form[x] + '"}}}},'

                    prop = prop[:-1] + ']'
            else:
                prop = '[]'
            row = { "name": form.name.data, "description": form.description.data,
                          "table_column": form.table_column.data,
                          "filter": form.filter.data , "enabled": status,
                          "group_name": form.group_name.data,
                          "prop": prop,
                          "rule": form.rule.data }

            etcd_conn.put('/rules/' + form.table_column.data.replace('.', '/') + '/' + form.group_name.data.replace('.', '/')+ '/' + form.name.data,
                          json.dumps(row))
            flash(_('Rule') + ' ' + _('Added'), 'info')
            return flask.redirect(flask.url_for('rules'))
        elif flask.request.args.get('key'):
            form_data = etcd_conn.get_list(flask.request.args.get('key'))
            i = 0
            prop = form_data.get('prop').replace('%col%', '"%col%"')
            for x in json.loads(prop):
                if x != "%col%":
                    obj = getattr(form, form.test.get(form_data.get('rule'))[i].replace('open_close_', ''))
                    try:
                        obj.data = x.get('A_Const').get('val').get("String").get("str")
                    except:
                        obj.data = x.get('A_Const').get('val')
                i = i + 1
            form.enabled.data = False
            if form_data.get('enabled') == 'true':
                form.enabled.data = True
            form.rule.data = form_data.get('rule')
            form.description.data = form_data.get('description')
            form.group_name.data = form_data.get('group_name')
            form.filter.data = form_data.get('filter')
            form.table_column.data = form_data.get('table_column')
            form.name.data = form_data.get('name')
            form.name.render_kw = {'readonly': True}
        return flask.render_template('rules.html', main_header=_('Rules'), form=form, button_list=button_list)

    elif url_type == 'delete':
        etcd_conn.delete(flask.request.args.get('key'))
        flash(_('Rule') + ' ' + _('Deleted'), 'error')

    group_list = etcd_conn.search('/rules/')
    headers = [_('Key'), _('Description'), _('Enabled'), _('Filter'), _('Table'), _('Group Name'),_('Name'), _('Properties'), _('Rule')]
    links = [{'name': _('Delete'), 'type': 'danger', 'link': '/rules/delete'},
            {'name': _('Update'), 'type': 'info', 'link': '/rules/change'}]

    return flask.render_template('list.html', main_header=_('Rules'), list=group_list, headers=headers,
                                 button_list=button_list, links=links)


@app.route('/groups', methods=['GET', 'POST'])
@app.route('/groups/<url_type>', methods=['GET', 'POST'])
@login_required
def groups(url_type=None):
    etcd_conn = Etcd()
    headers = [_('Name'), _('Description'), _('Enabled')]
    button_list = [{'name': _('New'), 'href': '/groups/change'}, {'name': _('List'), 'href': '/groups'}]
    if url_type == 'change':
        form = forms.GroupsForm()

        if form.validate_on_submit():
            status = 'false'
            if form.enabled.data is True:
                status = 'true'
            row = {"enabled": status, "desc": form.desc.data}
            etcd_conn.put('/groups/' + form.name.data.replace(' ', '_'),
                          json.dumps(row))
            flash(_('Group') + ' ' + _('Added'), 'info')
            return flask.redirect(flask.url_for('groups'))
        elif flask.request.args.get('key'):
            form_data = etcd_conn.get_list(flask.request.args.get('key'))
            form.enabled.data = False
            if form_data.get('enabled') == 'true':
                form.enabled.data = True
            form.desc.data = form_data.get('desc')
            form.name.data = flask.request.args.get('key').replace('/groups/', '')
            form.name.render_kw = {'readonly': True}
        return flask.render_template('list.html', main_header=_('Groups'), form=form, button_list=button_list)
    elif url_type == 'delete':
        etcd_conn.delete(flask.request.args.get('key'))
        flash(_('Group') + ' ' + _('Deleted'), 'error')
    group_list = etcd_conn.search('/groups/')
    links = [{'name': _('Delete'), 'type': 'danger', 'link': '/groups/delete'},
             {'name': _('Update'), 'type': 'info', 'link': '/groups/change'}]
    return flask.render_template('list.html', main_header=_('Groups'), list=group_list, headers=headers,
                                 button_list=button_list, links=links)


@app.route('/users', methods=['GET', 'POST'])
@app.route('/users/<url_type>', methods=['GET', 'POST'])
@login_required
def users(url_type=None):
    etcd_conn = Etcd()
    headers = [_('Name'), _('Enabled')]
    button_list = [{'name': _('New'), 'href': '/users/change'}, {'name': _('List'), 'href': '/users'}]
    if url_type == 'change':
        form = forms.DBorCommentUsersForm()
        if form.validate_on_submit():
            status = 'false'
            if form.enabled.data is True:
                status = 'true'
            row = {"enabled": status}
            etcd_conn.put('/users/' + form.user.data + '/' + form.group_name.data.replace('.', '/'),
                          json.dumps(row))
            flash(_('SQL User') + ' ' + _('Added'), 'info')
            return flask.redirect(flask.url_for('users'))
        elif flask.request.args.get('key'):
            form_data = etcd_conn.get_list(flask.request.args.get('key'))
            form.enabled.data = False
            if form_data.get('enabled') == 'true':
                form.enabled.data = True
            parse_name = flask.request.args.get('key').split('/')
            form.user.data = parse_name[2]
            form.user.render_kw = {'readonly': True}
            form.group_name.data = parse_name[3] + '.' + parse_name[4]
            form.group_name.render_kw = {'readonly': True}
        return flask.render_template('list.html', main_header=_('Users'), form=form, button_list=button_list)
    elif url_type == 'delete':
        etcd_conn.delete(flask.request.args.get('key'))
        flash(_('SQL User') + ' ' + _('Deleted'), 'error')
    group_list = etcd_conn.search('/users/')
    page = pagination(len(group_list))
    print(page)

    links = [{'name': _('Delete'), 'type': 'danger', 'link': '/users/delete'},
             {'name': _('Update'), 'type': 'info', 'link': '/users/change'}]
    return flask.render_template('list.html', main_header=_('Users'), list=group_list[(int(page.get('page')) - 1) * int(
        page.get('row_in_page')):((int(page.get('page')) - 1) * int(
        page.get('row_in_page'))) + int(page.get('row_in_page'))], headers=headers,
                                 button_list=button_list, links=links, pagination=page)


@app.route('/dbusers', methods=['GET', 'POST'])
@app.route('/dbusers/<url_type>', methods=['GET', 'POST'])
@login_required
def dbusers(url_type=None):
    etcd_conn = Etcd()
    headers = [_('Name'), _('Enabled')]
    button_list = [{'name': _('New'), 'href': '/dbusers/change'}, {'name': _('List'), 'href': '/dbusers'}]
    if url_type == 'change':
        form = forms.DBorCommentUsersForm()
        if form.validate_on_submit():
            status = 'false'
            if form.enabled.data is True:
                status = 'true'
            row = {"enabled": status}
            etcd_conn.put('/dbuser/' + form.user.data + '/' + form.group_name.data.replace('.', '/'),
                          json.dumps(row))
            flash(_('DB User') + ' ' + _('Added'), 'info')
            return flask.redirect(flask.url_for('dbusers'))
        elif flask.request.args.get('key'):
            form_data = etcd_conn.get_list(flask.request.args.get('key'))
            form.enabled.data = False
            if form_data.get('enabled') == 'true':
                form.enabled.data = True
            parse_name = flask.request.args.get('key').split('/')
            form.user.data = parse_name[2]
            form.user.render_kw = {'readonly': True}
            form.group_name.data = parse_name[3] + '.' + parse_name[4]
            form.group_name.render_kw = {'readonly': True}
        return flask.render_template('list.html', main_header=_('Users'), form=form, button_list=button_list)
    elif url_type == 'delete':
        etcd_conn.delete(flask.request.args.get('key'))
        flash(_('DB User') + ' ' + _('Deleted'), 'error')
    group_list = etcd_conn.search('/dbuser/')

    links = [{'name': _('Delete'), 'type': 'danger', 'link': '/dbusers/delete'},
             {'name': _('Update'), 'type': 'info', 'link': '/dbusers/change'}]
    return flask.render_template('list.html', main_header=_('Users'), list=group_list, headers=headers,
                                 button_list=button_list, links=links)


@app.route('/autocomplete', methods=['GET'])
@app.route('/autocomplete/<url_type>/<key>', methods=['GET'])
@login_required
def autocomplete(url_type=None, key=None):
    etcd_conn = Etcd()
    autocomplete_list = []
    if url_type == 'autocomplete_table':

        if key.count('.') == 0:
            fields = etcd_conn.search_keys('/' + key.replace('.', '/'))
            for i in fields:
                if i.split('.')[0] + '.' not in autocomplete_list:
                    autocomplete_list.append(i.split('.')[0] + '.')
        elif key.count('.') == 1:
            fields = etcd_conn.search_keys('/' + key.replace('.', '/'))
            for i in fields:
                if '.'.join(i.split('.')[0:2]) + '.' not in autocomplete_list:
                    autocomplete_list.append('.'.join(i.split('.')[0:2]) + '.')
        elif key.count('.') == 2:
            fields = etcd_conn.search_keys('/' + key.replace('.', '/'))
            for i in fields:
                if '.'.join(i.split('.')[0:3]) + '.' not in autocomplete_list:
                    autocomplete_list.append('.'.join(i.split('.')[0:3]) + '.')
        elif key.count('.') == 3:
            search_key = key.split('.')[-1]
            fields = etcd_conn.search('/' + '/'.join(key.split('.')[:-1]))
            for i in fields[0][0]:
                if i.get('column_name').find(search_key) > -1:
                    autocomplete_list.append('.'.join(key.split('.')[:-1]) + '.' + i.get('column_name'))

    else:
        autocomplete_list = etcd_conn.search_keys(
            '/' + url_type.replace('autocomplete_', '') + '/' + key.replace('.', '/'))
        # print(fields[0])
    return Response(json.dumps(autocomplete_list), mimetype='application/json')


@app.route('/user', methods=['GET', 'POST'])
@app.route('/user/<username>', methods=['GET', 'POST'])
@login_required
def user(username=None):
    form = forms.UserForm()

    if form.validate_on_submit():
        g.user.enabled = form.enabled.data
        g.user.locale = form.locale.data
        g.user.email = form.email.data
        if form.password.data:
            g.user.password_hash = g.user.hash_password(form.password.data)
            print(g.user.password_hash)
        g.user.set()
        flash(_('Admin User') + ' ' + _('Updated'), 'success')
    else:
        form.enabled.data = g.user.enabled
        # form.username.data = g.user.username
        form.locale.data = g.user.locale
        form.email.data = g.user.email
        form.password.data = None
    return flask.render_template('list.html', main_header=_('Admin User'), form=form)


@app.route('/pgbouncer', methods=['GET', 'POST'])
@login_required
def pgbouncer():
    from wtforms import StringField
    from wtforms import Label

    form_obj = []

    with open(config_filepath) as fp:
        line = fp.readline()
        cnt = 1
        text = ''
        write = 0
        while line:
            # print("Line {}: {}".format(cnt, line.strip()))
            line = fp.readline()
            if line.strip() == '[pgbouncer]':
                write = 1
            if write == 1:
                if line[0:3] == ';;;':
                    # setattr(forms.PgBouncerForm, "cc", Label("sdsa", line))
                    # setattr(forms.PgBouncerForm, parsed[0].strip(),
                    #         ReadOnlyField(parsed[0].strip(), default=parsed[1].strip(), description=text))
                    # text += '<h3>' + line[3:] + '</h3>'
                    pass
                elif line[0:2] == ';;':
                    text += line[2:]
                elif line[0:1] == ';':
                    parsed = line[1:].split('=')
                    text += '(' + _('Closed in config file') + ')'
                    # print(parsed)
                    if len(parsed) > 1:
                        form_obj.append(parsed[0].strip())
                        setattr(forms.PgBouncerForm, parsed[0].strip(),
                                StringField(parsed[0].strip(), default=parsed[1].strip(), description=text))
                    text = ''
                elif len(line.strip('\n')) > 0 and line.strip() != '[pgbouncer]':
                    parsed = line.strip('\n').split("=")
                    form_obj.append(parsed[0].strip())
                    setattr(forms.PgBouncerForm, parsed[0].strip(),
                            StringField(parsed[0].strip(), default=('='.join(parsed[1:])).strip(), description=text))
                    text = ''

            cnt += 1
    form = forms.PgBouncerForm()

    for i in form_obj:
        delattr(forms.PgBouncerForm, i)

    return flask.render_template('list.html', main_header=_('PgBouncer Config'), form=form)


@app.route('/sqlfilter', methods=['GET', 'POST'])
@app.route('/sqlfilter/<url_type>', methods=['GET', 'POST'])
@login_required
def sqlfilter(url_type=None):
    etcd_conn = Etcd()
    button_list = [{'name': _('New'), 'href': '/sqlfilter/change'}, {'name': _('List'), 'href': '/sqlfilter'}]
    if url_type == 'change':
        form = forms.SQLFilterForm()
        if form.validate_on_submit():
            enabled = 'false'
            if form.enabled.data:
                enabled = 'true'
            if form.group_name.data == '':
                form.group_name.data = '*'
            row = { "filter": form.filter.data, "group_name": form.group_name.data, "enabled": enabled }
            etcd_conn.put('/sqlfilter/' + form.table.data.replace('.', '/') + '/' + form.group_name.data.replace('.', '/'),
                json.dumps(row))
            flash(_('SQL Filter') + ' ' + _('Added'), 'info')
            return flask.redirect(flask.url_for('sqlfilter'))
        elif flask.request.args.get('key'):
            form_data = etcd_conn.get_list(flask.request.args.get('key'))
            form.enabled.data = False
            if form_data.get('enabled') == 'true':
                form.enabled.data = True
            form.filter.data = form_data.get('filter')
            form.group_name.data = form_data.get('group_name')
            form.table.data = flask.request.args.get('key').replace('/sqlfilter/', '').replace('/', '.').replace('.'+form_data.get('group_name'), '')
            form.group_name.render_kw = {'readonly': True}
            form.table.render_kw = {'readonly': True}
        return flask.render_template('list.html', main_header=_('SQL Filter'), form=form, button_list=button_list)
    elif url_type == 'delete':
        etcd_conn.delete(flask.request.args.get('key'))
        flash(_('SQL Filter') + ' ' + _('Deleted'), 'error')

    group_list = etcd_conn.search('/sqlfilter/')
    headers = [_('Table'), _('Enabled'), _('SQL Filter'), _('Group Name')]
    links = [{'name': _('Delete'), 'type': 'danger', 'link': '/sqlfilter/delete'},
             {'name': _('Update'), 'type': 'info', 'link': '/sqlfilter/change'}]

    return flask.render_template('list.html', main_header=_('SQL Filter'), list=group_list, headers=headers,
                                 button_list=button_list, links=links)


app.run(debug=True, host="0.0.0.0", port=25432)
