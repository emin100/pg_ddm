import configparser
import os
import re
from urllib.parse import urlparse, urljoin

import flask
import psycopg2
from flask import Flask, render_template, redirect, url_for, session, flash, Response, json, request, g
from flask_babel import Babel, _
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, logout_user, login_required, login_user

import forms
from etcd import Etcd
from models import User

babel = Babel()
login_manager = LoginManager()
config_filepath = os.path.dirname(os.path.abspath(__file__)) + '/conf/settings.cfg'
config = configparser.RawConfigParser(allow_no_value=True)
config.read(config_filepath)


def check_roles(url):
    url = (url.split('/'))[-1]
    if url in ['login', 'logout', ''] or request.endpoint == 'static':
        return True
    logined_user = g.user
    if url in ['change', 'delete'] and logined_user.role not in ['admin', 'editor']:
        return False
    elif url in ['system_users', 'pg_ddm', 'external_services'] and logined_user.role not in ['admin']:
        return False
    else:
        return True


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
    app_obj.config['ETCD_SETTINGS'] = config['etcd']

    app_obj.jinja_env.globals.update(check_roles=check_roles)

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


def pagination(total, extra=''):
    import math
    page = 1
    row_in_page = int(config['general']['row_in_page'])
    total_page = math.ceil(total / row_in_page)

    if request.args.get('page') is not None:
        page = int(request.args.get('page'))
    if request.args.get('submit') is not None and request.args.get('submit') == _('Search'):
        page = int(1)
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

    return {'total': total, 'page': page, 'total_page': total_page, 'row_in_page': row_in_page, 'start': start,
            'end': end, 'extra': extra}


def get_calculated_page(data_list, page):
    return data_list[(int(page.get('page')) - 1) * int(
        page.get('row_in_page')): ((int(page.get('page')) - 1) * int(
        page.get('row_in_page'))) + int(page.get('row_in_page'))]


def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def remove_dependency(key):
    etcd_conn = Etcd()
    for record in etcd_conn.search('/', search_key=key):
        record_key = record[1].key.decode('utf-8')
        record_split = re.split(key, record_key)
        if not record_split[1] or record_split[1][:1] == '/':
            etcd_conn.delete(record_key)

    pass


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


@app.after_request
def after_request_func(response):
    if check_roles(request.base_url):
        return response
    else:
        flash(_('Acsess Denied.'), 'danger')
        return redirect(url_for('index'))


@login_manager.user_loader
def load_user(user_id):
    loaded_user = User(user_id)
    g.user = loaded_user
    # check_roles()

    return loaded_user


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


@app.route('/external_services', methods=['GET', 'POST'])
@app.route('/external_services/<url_type>', methods=['GET', 'POST'])
@login_required
def external_services(url_type=None):
    etcd_conn = Etcd()
    headers = [(_('Name'), 'name'), (_('Enabled'), 'enabled')]
    button_list = [{'name': _('New'), 'href': '/external_services/change'},
                   {'name': _('List'), 'href': '/external_services'}]
    if url_type == 'change':
        form = forms.ServicesForm()

        if form.validate_on_submit():
            status = 'false'
            if form.enabled.data is True:
                status = 'true'
            row = {"enabled": status, "name": form.name.data, "role_service_url": form.role_service_url.data,
                   "role_service_param": form.role_service_param.data, "role_service_key": form.role_service_key.data,
                   "role_service_value": form.role_service_value.data, "user_service_url": form.user_service_url.data,
                   "user_service_key": form.user_service_key.data, "user_service_param": form.user_service_param.data,
                   "username": form.username.data, "password": form.password.data
                   }
            etcd_conn.put('/services/' + form.name.data.lower().replace(' ', '_'),
                          json.dumps(row))
            flash(_('Service') + ' ' + _('Added') + ' / ' + _('Updated'), 'info')
            return flask.redirect(flask.url_for('external_services'))
        elif flask.request.args.get('key'):
            form_data = etcd_conn.get_list(flask.request.args.get('key'))
            form.enabled.data = False
            if form_data.get('enabled') == 'true':
                form.enabled.data = True
            form.role_service_url.data = form_data.get('role_service_url')
            form.role_service_param.data = form_data.get('role_service_param')
            form.role_service_key.data = form_data.get('role_service_key')
            form.role_service_value.data = form_data.get('role_service_value')
            form.user_service_url.data = form_data.get('user_service_url')
            form.user_service_key.data = form_data.get('user_service_key')
            form.user_service_param.data = form_data.get('user_service_param')
            form.username.data = form_data.get('username')
            form.password.data = form_data.get('password')
            # form.name.data = flask.request.args.get('key').replace('/services/', '')
            form.name.data = form_data.get('name')
            form.name.render_kw = {'readonly': True}
        return flask.render_template('list.html', main_header=_('Register Services'), form=form,
                                     button_list=button_list)
    elif url_type == 'delete':
        etcd_conn.delete(flask.request.args.get('key'))
        flash(_('Service') + ' ' + _('Deleted'), 'error')
        return flask.redirect(flask.url_for('external_services'))
    group_list = etcd_conn.search('/services/')
    page = pagination(len(group_list))
    links = [{'name': _('Delete'), 'type': 'danger', 'link': '/external_services/delete'},
             {'name': _('Update'), 'type': 'info', 'link': '/external_services/change'}]
    return flask.render_template('list.html', main_header=_('Services'),
                                 list=get_calculated_page(group_list, page), pagination=page,
                                 button_list=button_list, links=links, headers=headers)


@app.route('/role_to_group', methods=['GET', 'POST'])
@app.route('/role_to_group/<url_type>', methods=['GET', 'POST'])
@login_required
def role_to_group(url_type=None):
    etcd_conn = Etcd()
    button_list = [{'name': _('New'), 'href': '/role_to_group/change'}, {'name': _('List'), 'href': '/role_to_group'}]
    header = [(_('Services'), 'service_key'), (_('Group Name'), 'group'), (_('Enabled'), 'enabled')]
    if url_type == 'change':
        form = forms.RoleForm()
        service_list = [(None, _('Select'))]
        for x in etcd_conn.search('/services'):
            service_list.append((str(x[1].key.decode("utf-8")), str(x[0].get('name'))))
        form.service.choices = service_list
        if form.validate_on_submit():
            try:
                status = 'false'
                if form.enabled.data:
                    status = 'true'
                key = '/role_to_group/' + form.group_name.data.replace('.', '/') + "/" + str(form.role_id.data)
                etcd_conn.put(key, json.dumps(
                    {"enabled": status, "group": form.role.data, "service_key": form.service.data}))
            except Exception as error:
                print(error)

            flash(_('Role to Group') + ' ' + _('Added') + ' / ' + _('Updated'), 'success')
            return flask.redirect('/role_to_group/refresh?key={}'.format(key))
        elif flask.request.args.get('key'):
            parse_key = flask.request.args.get('key').split('/')
            form_data = etcd_conn.get_list(flask.request.args.get('key'))
            form.enabled.data = False
            if form_data.get('enabled') == 'true':
                form.enabled.data = True
            form.service.data = form_data.get('service_key')
            form.group_name.data = parse_key[2] + '.' + parse_key[3]
            form.role.data = form_data.get('group')
            form.role_id.data = parse_key[4]
            form.service.render_kw = {'readonly': True}
            form.group_name.render_kw = {'readonly': True}
            form.role.render_kw = {'readonly': True}
        return flask.render_template('role.html', main_header=_('Role to Group'), form=form, button_list=button_list)
    elif url_type == 'delete':
        parse_key = flask.request.args.get('key').split('/')
        for x in etcd_conn.get_prefix('/users/', sort_order="ascend", sort_target="key"):
            parse_user_key = str(x[1].key.decode("utf-8")).split('/')
            # print(parse_user_key)
            if parse_user_key[3] == parse_key[2] and parse_user_key[4] == parse_key[3]:
                etcd_conn.delete(x[1].key.decode("utf-8"))
        etcd_conn.delete(flask.request.args.get('key'))
        flash(_('Role to Group') + ' ' + _('Deleted'), 'error')
        return flask.redirect('/role_to_group')
    elif url_type == 'refresh':
        key = flask.request.args.get('key')
        parse_key = key.split('/')
        role_to_group = etcd_conn.get_list(key)

        status = role_to_group.get('enabled')

        service = etcd_conn.get_list(role_to_group.get('service_key'))
        import requests

        r = requests.post(service.get('user_service_url'),
                          json={service.get('user_service_param'): parse_key[4]},
                          auth=(service.get('username'), service.get('password')))
        for row in r.json():
            id = row.get(service.get('user_service_key'))
            key = '/users/{}/{}/{}'.format(str(id), parse_key[2], parse_key[3])
            try:
                user = etcd_conn.get_list(key)
                if user.get('enabled') != status:
                    etcd_conn.put(key, json.dumps({"enabled": status}))
            except:
                etcd_conn.put(key, json.dumps({"enabled": status}))

        flash(_('Role to Group') + ' ' + _('Refreshed'), 'success')
        return flask.redirect('/role_to_group')
    group_list = etcd_conn.search('/role_to_group/')
    page = pagination(len(group_list))
    links = [{'name': _('Delete'), 'type': 'danger', 'link': '/role_to_group/delete'},
             {'name': _('Update'), 'type': 'info', 'link': '/role_to_group/change'},
             {'name': _('Refresh'), 'type': 'success', 'link': '/role_to_group/refresh'}]
    return flask.render_template('list.html', main_header=_('Role to Group'), button_list=button_list,
                                 list=get_calculated_page(group_list, page), headers=header,
                                 links=links, pagination=page)


@app.route('/dbmeta', methods=['GET', 'POST'])
@app.route('/dbmeta/<url_type>', methods=['GET', 'POST'])
@login_required
def dbmeta(url_type=None):
    etcd_conn = Etcd()
    try:
        pg_ddm_config = configparser.RawConfigParser(allow_no_value=True)

        if str(config['general']['get_db_info_in_pg_ddm_config_file']).lower() == 'true':
            pg_ddm_config.read(config['general']['pg_ddm_config_file_path'])
            databases = pg_ddm_config['databases']
        else:
            databases = config['database']

        db_list = []
        conn_info = {}
        for db in databases:
            db_list.append((db, db))
            key_list = {}
            tmp_dsn = []
            for i in databases[db].split(" "):
                key = i.split("=")
                if key[0] != 'search_path' and key[0] != 'route':
                    tmp_dsn.append(key[0] + '=' + key[1])
                    key_list[key[0]] = key[1]
            conn_info[db] = key_list
            databases[db] = ' '.join(tmp_dsn)

        form = forms.TableSelectForm()
        form.db.choices = db_list

        button_list = [{'name': _('Refresh'), 'href': '/dbmeta/change'}, {'name': _('List'), 'href': '/dbmeta'}]

        # if url_type == 'update':
        #     print('update')
        if url_type == 'change':
            if form.validate_on_submit():
                form_cred = forms.TablesForm()
                if form.db.data is not None:
                    if 'user' in conn_info[form.db.data]:
                        form_cred.username.data = conn_info[form.db.data]['user']
                    if 'password' in conn_info[form.db.data]:
                        form_cred.password.data = conn_info[form.db.data]['password']
                form_cred.db.data = form.db.data

                if form_cred.validate_on_submit():
                    conn = None
                    try:
                        db = databases[form.db.data]
                        conn = psycopg2.connect(db, user=form_cred.username.data, password=form_cred.password.data)
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
                            etcd_conn.put(key, json.dumps(row[3]))
                        cur.close()
                    except (Exception, psycopg2.DatabaseError) as e:
                        flash(_('DB Error'), e)
                    except (Exception, psycopg2.DatabaseError) as e:
                        flash(_('General Error'), e)
                    finally:
                        if conn is not None:
                            conn.close()

                    flash(_('Database Metadata') + ' ' + _('Updated'), 'info')
                    return flask.redirect(flask.url_for('dbmeta'))
                return flask.render_template('list.html', main_header=_('Database connection'), form=form_cred,
                                             button_list=button_list)
            return flask.render_template('list.html', main_header=_('Database select'), form=form,
                                         button_list=button_list)
        else:
            if form.validate_on_submit() or request.args.get('db'):
                if request.args.get('db') is not None:
                    db = request.args.get('db')
                else:
                    db = str(form.db.data)
                group_list = etcd_conn.search('/{}/'.format(db), json_field=False)
                headers = [(_('Columns'), '')]
                # links = [{'name': _('Update'), 'type': 'info', 'link': '/dbmeta/update'}]
                links = []
                extra_param = '&db=' + str(db)
                if request.args.get('search_key') is not None and request.args.get('search_key'):
                    extra_param += '&search_key=' + str(request.args.get('search_key')) + '&search_type=' + str(
                        request.args.get('search_type'))
                page = pagination(len(group_list), extra_param)

                return flask.render_template('list.html', main_header=_('Database Metadata'),
                                             list=get_calculated_page(group_list, page), pagination=page,
                                             headers=headers,
                                             links=links, button_list=button_list)
            return flask.render_template('list.html', main_header=_('Database Metadata'), form=form,
                                         button_list=button_list)
    except FileNotFoundError:
        flash(_('pg_ddm config file not found'), 'error')
    except KeyError:
        flash(_('pg_ddm_config_file_path key not found in settings.cfg'), 'warning')

    return flask.render_template('list.html', main_header=_('Database Metadata'))


@app.route('/rules', methods=['GET', 'POST'])
@app.route('/rules/<url_type>', methods=['GET', 'POST'])
@login_required
def rules(url_type=None):
    etcd_conn = Etcd()
    button_list = [{'name': _('New'), 'href': '/rules/change'}, {'name': _('List'), 'href': '/rules'}]
    headers = [(_('Description'), 'description'), (_('Group Name'), 'group_name'), (_('Table'), 'table_column'),
               (_('Enabled'), 'enabled')]
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
            row = {"name": form.name.data, "description": form.description.data,
                   "table_column": form.table_column.data,
                   "filter": form.filter.data, "enabled": status,
                   "group_name": form.group_name.data,
                   "prop": prop,
                   "rule": form.rule.data}

            etcd_conn.put('/rules/' + form.table_column.data.replace('.', '/') + '/' + form.group_name.data.replace('.',
                                                                                                                    '/') + '/' + form.name.data,
                          json.dumps(row))
            flash(_('Rule') + ' ' + _('Added') + ' / ' + _('Updated'), 'info')
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
            form.table_column.render_kw = {'readonly': True}
            form.group_name.render_kw = {'readonly': True}
        return flask.render_template('rules.html', main_header=_('Rules'), form=form, button_list=button_list)

    elif url_type == 'delete':
        etcd_conn.delete(flask.request.args.get('key'))
        flash(_('Rule') + ' ' + _('Deleted'), 'error')
        return flask.redirect(flask.url_for('rules'))

    group_list = etcd_conn.search('/rules/')
    page = pagination(len(group_list))
    links = [{'name': _('Delete'), 'type': 'danger', 'link': '/rules/delete'},
             {'name': _('Update'), 'type': 'info', 'link': '/rules/change'}]

    return flask.render_template('list.html', main_header=_('Rules'),
                                 list=get_calculated_page(group_list, page),
                                 pagination=page, headers=headers,
                                 button_list=button_list, links=links)


@app.route('/groups', methods=['GET', 'POST'])
@app.route('/groups/<url_type>', methods=['GET', 'POST'])
@login_required
def groups(url_type=None):
    etcd_conn = Etcd()
    headers = [(_('Description'), 'desc'), (_('Enabled'), 'enabled')]
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
            flash(_('Group') + ' ' + _('Added') + ' / ' + _('Updated'), 'info')
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
        remove_dependency(flask.request.args.get('key'))
        flash(_('Group') + ' ' + _('Deleted'), 'error')
        # return flask.redirect(flask.url_for('groups'))
    group_list = etcd_conn.search('/groups/')
    page = pagination(len(group_list))
    links = [{'name': _('Delete'), 'type': 'danger', 'link': '/groups/delete'},
             {'name': _('Update'), 'type': 'info', 'link': '/groups/change'}]
    return flask.render_template('list.html', main_header=_('Groups'),
                                 list=get_calculated_page(group_list, page), pagination=page,
                                 headers=headers, button_list=button_list, links=links)


@app.route('/system_users', methods=['GET', 'POST'])
@app.route('/system_users/<url_type>', methods=['GET', 'POST'])
@login_required
def system_users(url_type=None):
    etcd_conn = Etcd()
    headers = [(_('Username'), 'username'), (_('Role'), 'role'), (_('Enabled'), 'enabled')]
    button_list = [{'name': _('New'), 'href': '/system_users/change'}, {'name': _('List'), 'href': '/system_users'}]
    if url_type == 'change':
        form = forms.UserForm()
        if form.validate_on_submit():
            status = False
            if form.enabled.data is True:
                status = True
            row = {"enabled": status, "locale": form.locale.data, "email": form.email.data,
                   "username": form.username.data, "role": form.role.data}
            if flask.request.args.get('key'):
                if form.password.data:
                    row['password'] = g.user.hash_password(form.password.data)
                else:
                    form_data = etcd_conn.get_list(flask.request.args.get('key'))
                    row['password'] = form_data.get('password')
            else:
                row['password'] = g.user.hash_password(form.password.data)
            etcd_conn.put('/appuser/' + form.username.data, json.dumps(row))
            flash(_('System User') + ' ' + _('Added') + ' / ' + _('Updated'), 'info')
            return flask.redirect(flask.url_for('system_users'))
        elif flask.request.args.get('key'):
            form_data = etcd_conn.get_list(flask.request.args.get('key'))
            form.enabled.data = False
            if form_data.get('enabled') is True:
                form.enabled.data = True
            form.username.render_kw = {'readonly': True}
            form.email.data = form_data.get('email')
            form.locale.data = form_data.get('locale')
            form.username.data = form_data.get('username')
            form.role.data = form_data.get('role')
        return flask.render_template('list.html', main_header=_('Users'), form=form, button_list=button_list)
    elif url_type == 'delete':
        etcd_conn.delete(flask.request.args.get('key'))
        flash(_('SQL User') + ' ' + _('Deleted'), 'error')
        return flask.redirect(flask.url_for('system_users'))
    group_list = etcd_conn.search('/appuser/')
    page = pagination(len(group_list))

    links = [{'name': _('Delete'), 'type': 'danger', 'link': '/system_users/delete'},
             {'name': _('Update'), 'type': 'info', 'link': '/system_users/change'}]
    return flask.render_template('list.html', main_header=_('SQL Users'),
                                 list=get_calculated_page(group_list, page), headers=headers,
                                 button_list=button_list, links=links, pagination=page)


@app.route('/users', methods=['GET', 'POST'])
@app.route('/users/<url_type>', methods=['GET', 'POST'])
@login_required
def users(url_type=None):
    etcd_conn = Etcd()
    headers = [(_('Enabled'), 'enabled')]
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
            flash(_('SQL User') + ' ' + _('Added') + ' / ' + _('Updated'), 'info')
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
        return flask.redirect(flask.url_for('users'))
    group_list = etcd_conn.search('/users/')
    page = pagination(len(group_list))

    links = [{'name': _('Delete'), 'type': 'danger', 'link': '/users/delete'},
             {'name': _('Update'), 'type': 'info', 'link': '/users/change'}]
    return flask.render_template('list.html', main_header=_('SQL Users'),
                                 list=get_calculated_page(group_list, page), headers=headers,
                                 button_list=button_list, links=links, pagination=page)


@app.route('/dbusers', methods=['GET', 'POST'])
@app.route('/dbusers/<url_type>', methods=['GET', 'POST'])
@login_required
def dbusers(url_type=None):
    etcd_conn = Etcd()
    headers = [(_('Enabled'), 'enabled')]
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
            flash(_('DB User') + ' ' + _('Added') + ' / ' + _('Updated'), 'info')
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
        return flask.redirect(flask.url_for('dbusers'))
    group_list = etcd_conn.search('/dbuser/')
    page = pagination(len(group_list))

    links = [{'name': _('Delete'), 'type': 'danger', 'link': '/dbusers/delete'},
             {'name': _('Update'), 'type': 'info', 'link': '/dbusers/change'}]
    return flask.render_template('list.html', main_header=_('DB Users'),
                                 list=get_calculated_page(group_list, page), headers=headers,
                                 button_list=button_list, links=links, pagination=page)


@app.route('/autocomplete', methods=['GET'])
@app.route('/autocomplete/<url_type>/<key>', methods=['GET'])
@login_required
def autocomplete(url_type=None, key=None):
    etcd_conn = Etcd()
    autocomplete_list = []
    if url_type == 'autocomplete_table' or url_type == 'autocomplete_table_without_columns':

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
                    dot = ''
                    if url_type == 'autocomplete_table':
                        dot = '.'
                    autocomplete_list.append('.'.join(i.split('.')[0:3]) + dot)
        elif key.count('.') == 3 and url_type == 'autocomplete_table':
            search_key = key.split('.')[-1]
            fields = etcd_conn.search('/' + '/'.join(key.split('.')[:-1]))
            for i in fields[0][0]:
                if i.get('column_name').find(search_key) > -1:
                    autocomplete_list.append('.'.join(key.split('.')[:-1]) + '.' + i.get('column_name'))
    elif url_type == 'autocomplete_role':
        service_key = request.args.get("service")
        if service_key is not None:
            service = etcd_conn.get_list(service_key)
            import requests
            r = requests.post(service.get('role_service_url'), json={service.get('role_service_param'): key},
                              auth=(service.get('username'), service.get('password')))
            for row in r.json():
                autocomplete_list.append({"value": row.get(service.get('role_service_key')),
                                          "label": row.get(service.get('role_service_value'))})
    else:
        autocomplete_list = etcd_conn.search_keys(
            '/' + url_type.replace('autocomplete_', '') + '/' + key.replace('.', '/'))

    return Response(json.dumps(autocomplete_list), mimetype='application/json')


@app.route('/user', methods=['GET', 'POST'])
@login_required
def user():
    form = forms.UserForm()

    if form.validate_on_submit():
        # g.user.enabled = form.enabled.data
        g.user.locale = form.locale.data
        g.user.email = form.email.data
        if form.password.data:
            g.user.password_hash = g.user.hash_password(form.password.data)
            # print(g.user.password_hash)
        g.user.set()
        flash(_('User Info') + ' ' + _('Updated'), 'success')
    else:
        form.enabled.data = g.user.enabled
        # form.username.data = g.user.username
        form.locale.data = g.user.locale
        form.email.data = g.user.email
        form.password.data = None
    form.username.data = g.user.username
    form.role.data = g.user.role
    form.username.render_kw = {'readonly': True}
    form.role.render_kw = {'readonly': True}
    form.enabled.render_kw = {'readonly': True}
    return flask.render_template('list.html', main_header=_('User Info'), form=form)


@app.route('/pg_ddm', methods=['GET', 'POST'])
@login_required
def pg_ddm():
    from wtforms import StringField
    form = None
    try:
        form_obj = []

        with open(config['general']['pg_ddm_config_file_path']) as fp:
            line = fp.readline()
            cnt = 1
            text = ''
            header = ''
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
                        header += '<h3>' + line[3:] + '</h3>'
                        pass
                    elif line[0:2] == ';;':
                        text += line[2:]
                    elif line[0:1] == ';':
                        parsed = line[1:].split('=')
                        text += '(' + _('Closed in config file') + ')'
                        # print(parsed)
                        if len(parsed) > 1:
                            text += header
                            form_obj.append(parsed[0].strip())
                            setattr(forms.PgBouncerForm, parsed[0].strip(),
                                    StringField(parsed[0].strip(), default=parsed[1].strip(), description=text))
                        text = ''
                        header = ''
                    elif len(line.strip('\n')) > 0 and line.strip() != '[pgbouncer]':
                        parsed = line.strip('\n').split("=")
                        form_obj.append(parsed[0].strip())
                        text += header
                        setattr(forms.PgBouncerForm, parsed[0].strip(),
                                StringField(parsed[0].strip(), default=('='.join(parsed[1:])).strip(),
                                            description=text))
                        text = ''
                        header = ''

                cnt += 1
            form = forms.PgBouncerForm()

            for i in form_obj:
                delattr(forms.PgBouncerForm, i)
    except FileNotFoundError:
        flash(_('pg_ddm config file not found'), 'error')
    except KeyError:
        flash(_('pg_ddm_config_file_path key not found in settings.cfg'), 'warning')

    return flask.render_template('list.html', main_header=_('PgDdm Config'), form=form)


@app.route('/sqlfilter', methods=['GET', 'POST'])
@app.route('/sqlfilter/<url_type>', methods=['GET', 'POST'])
@login_required
def sqlfilter(url_type=None):
    etcd_conn = Etcd()
    button_list = [{'name': _('New'), 'href': '/sqlfilter/change'}, {'name': _('List'), 'href': '/sqlfilter'}]
    headers = [(_('SQL Filter'), 'filter'), (_('Group Name'), 'group_name'), (_('Enabled'), 'enabled')]
    if url_type == 'change':
        form = forms.SQLFilterForm()
        if form.validate_on_submit():
            enabled = 'false'
            if form.enabled.data:
                enabled = 'true'
            if form.group_name.data == '':
                form.group_name.data = '*'
            row = {"filter": form.filter.data, "group_name": form.group_name.data, "enabled": enabled}
            etcd_conn.put(
                '/sqlfilter/' + form.table.data.replace('.', '/') + '/' + form.group_name.data.replace('.', '/'),
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
            form.table.data = flask.request.args.get('key').replace('/sqlfilter/', '').replace('/', '.').replace(
                '.' + form_data.get('group_name'), '')
            form.group_name.render_kw = {'readonly': True}
            form.table.render_kw = {'readonly': True}
        return flask.render_template('list.html', main_header=_('SQL Filter'), form=form, button_list=button_list)
    elif url_type == 'delete':
        etcd_conn.delete(flask.request.args.get('key'))
        flash(_('SQL Filter') + ' ' + _('Deleted'), 'error')
        return flask.redirect(flask.url_for('sqlfilter'))

    group_list = etcd_conn.search('/sqlfilter/')
    page = pagination(len(group_list))
    links = [{'name': _('Delete'), 'type': 'danger', 'link': '/sqlfilter/delete'},
             {'name': _('Update'), 'type': 'info', 'link': '/sqlfilter/change'}]

    return flask.render_template('list.html', main_header=_('SQL Filter'), list=get_calculated_page(group_list, page),
                                 headers=headers,
                                 button_list=button_list, links=links, pagination=page)


app.run(debug=config.get('general', 'debug'), host=config.get('general', 'host'), port=config.get('general', 'port'))
