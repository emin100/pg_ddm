import datetime

from flask import json
from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField, HiddenField
from wtforms.fields.html5 import DateField, IntegerField, EmailField
from wtforms.validators import DataRequired


class LoginForm(FlaskForm):
    username = StringField(lazy_gettext(u'Username'), validators=[DataRequired()],
                           render_kw={"placeholder": lazy_gettext(u'Username')})
    password = PasswordField(lazy_gettext(u'Password'), validators=[DataRequired()],
                             render_kw={"placeholder": lazy_gettext(u'Password')})
    remember_me = BooleanField(lazy_gettext(u'Remember me'))
    submit = SubmitField(lazy_gettext(u'Sign in'))


class RulesForm(FlaskForm):
    test = {'partial': ['open_close_col', 'open_close_prefix_length', 'open_close_padding', 'open_close_suffix_length'],
            'random_date_between': ['open_close_start_date', 'open_close_end_date'],
            'random_phone': ['open_close_prefix'],
            'random_string': ['open_close_length'],
            'partial_email': ['open_close_col'],
            'random_int_between': ['open_close_start', 'open_close_end']}
    name = StringField(lazy_gettext('Name'), id="filter", validators=[DataRequired()],
                                          description=lazy_gettext("Don't use any blank or special character. This field use like a id"))
    description = StringField(lazy_gettext('Description'), id="description")
    group_name = StringField(lazy_gettext('Group Name'), id="autocomplete_groups", validators=[DataRequired()],
                             description=lazy_gettext('Please search like this(DB.SCHEMA.TABLE.COLUMN)'))
    filter = StringField(lazy_gettext('Filter'), id="filter",
                                          description=lazy_gettext('SQL Filter'))
    table_column = StringField(lazy_gettext('Table Column'), id="autocomplete_table", validators=[DataRequired()],
                        description=lazy_gettext('Please search like this(DB.SCHEMA.TABLE.COLUMN)'))
    enabled = BooleanField(lazy_gettext('Enabled'), default='true')
    rule = SelectField(lazy_gettext('Rule'),
                       choices=[['send_null', lazy_gettext('Send Null')], ['delete_col', lazy_gettext('Delete Column')],
                                ['partial', lazy_gettext('Partial')], ['partial_email', lazy_gettext('Partial Email')],
                                ['random_date', lazy_gettext('Random Date')],
                                ['random_date_between', lazy_gettext('Random Date Between')],
                                ['random_int_between', lazy_gettext('Random Int Between')],
                                ['random_phone', lazy_gettext('Random Phone')],
                                ['random_string', lazy_gettext('Random String')],
                                ['random_zip', lazy_gettext('Random Zip')]], validators=[DataRequired()],
                       render_kw={"onchange": "test($(this).val()," + json.dumps(test) + ",'open_close')"})
    start_date = DateField(lazy_gettext('Start Date'), format='%Y-%m-%d', default=datetime.datetime(1900, 1, 1),
                           id="open_close_start_date",
                           render_kw={'hidden': True, 'required': False})
    end_date = DateField(lazy_gettext('End Date'), format='%Y-%m-%d', default=datetime.datetime.now(),
                         id="open_close_end_date",
                         render_kw={'hidden': True})
    start = IntegerField(lazy_gettext('Start'), id="open_close_start", render_kw={'hidden': True}, default=0)
    end = IntegerField(lazy_gettext('End'), id="open_close_end", render_kw={'hidden': True}, default=0)
    prefix = StringField(lazy_gettext('Prefix'), id="open_close_prefix", render_kw={'hidden': True}, default="")
    prefix_length = IntegerField(lazy_gettext('Prefix'), id="open_close_prefix_length", render_kw={'hidden': True},
                                 default=0)
    suffix_length = IntegerField(lazy_gettext('Suffix'), id="open_close_suffix_length", render_kw={'hidden': True},
                                 default=0)
    padding = StringField(lazy_gettext('Padding'), id="open_close_padding", render_kw={'hidden': True}, default="")
    length = IntegerField(lazy_gettext('Length'), id="open_close_length", render_kw={'hidden': True}, default=0)
    col = HiddenField(id="open_close_col", render_kw={'hidden': True})
    submit = SubmitField(lazy_gettext(u'Submit'))


class GroupsForm(FlaskForm):
    name = StringField(lazy_gettext('Name'), validators=[DataRequired()])
    enabled = BooleanField(lazy_gettext('Enabled'), default='true')
    desc = StringField(lazy_gettext('Description'), validators=[DataRequired()])
    submit = SubmitField(lazy_gettext(u'Submit'))


class DBorCommentUsersForm(FlaskForm):
    group_name = StringField(lazy_gettext('Group Name'), id="autocomplete_groups", validators=[DataRequired()])
    user = StringField(lazy_gettext('User ID'), validators=[DataRequired()])
    enabled = BooleanField(lazy_gettext('Enabled'), default='true')
    submit = SubmitField(lazy_gettext(u'Submit'))


class RoleForm(FlaskForm):
    role = StringField(lazy_gettext('Group Name'), id="autocomplete_role", validators=[DataRequired()])
    group_name = StringField(lazy_gettext('Group Name'), id="autocomplete_groups", validators=[DataRequired()])
    role_id = HiddenField(lazy_gettext('Group Name'), id="role", validators=[DataRequired()])
    enabled = BooleanField(lazy_gettext('Enabled'), default='true')
    submit = SubmitField(lazy_gettext(u'Submit'))


class UserForm(FlaskForm):
    enabled = BooleanField(lazy_gettext('Enabled'))
    locale = SelectField(lazy_gettext('Language'), choices=(('en', 'English'), ('tr', 'Türkçe')),
                         validators=[DataRequired()])
    password = PasswordField(lazy_gettext('Password'))
    email = EmailField(lazy_gettext('E-mail'), validators=[DataRequired()])
    # username = StringField(lazy_gettext('Username'), validators=[DataRequired()])
    submit = SubmitField(lazy_gettext(u'Submit'))


class PgBouncerForm(FlaskForm):
    pass


class TableSelectForm(FlaskForm):
    db = SelectField(lazy_gettext('Database'), validators=[DataRequired()])
    submit = SubmitField(lazy_gettext(u'Submit'))


class TablesForm(FlaskForm):
    db = SelectField(lazy_gettext('Database'), validators=[DataRequired()])
    username = StringField(lazy_gettext('User'), validators=[DataRequired()])
    password = PasswordField(lazy_gettext('Password'), validators=[DataRequired()])
    # remember = BooleanField(lazy_gettext('Remember'))
    submit = SubmitField(lazy_gettext(u'Submit'))


class PassTagForm(FlaskForm):
    tag = StringField(lazy_gettext('Tag'), validators=[DataRequired()])
    enabled = BooleanField(lazy_gettext('Enabled'), default='true')
    submit = SubmitField(lazy_gettext(u'Submit'))


class SQLFilterForm(FlaskForm):
    table = StringField(lazy_gettext('Table'), id="autocomplete_table", validators=[DataRequired()],
                        description=lazy_gettext('Please search like this(DB.SCHEMA.TABLE)'))

    filter = StringField(lazy_gettext('SQL Filter'), validators=[DataRequired()])
    enabled = BooleanField(lazy_gettext('Enabled'), default='true')

    submit = SubmitField(lazy_gettext(u'Submit'))
