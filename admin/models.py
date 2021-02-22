import hashlib

from flask import json
from flask_login import UserMixin
from pytz import unicode

from etcd import Etcd


class User(UserMixin):
    etcd = None
    password = None
    username = None
    password_hash = None
    secret = "89660c74da48ddd4efbe4d3c8f8150de"
    locale = 'tr'
    enabled = False
    email = None
    role = 'viewer'

    def __init__(self, username, password=None, etcd=None):
        self.etcd = Etcd()
        self.username = username
        self.password = self.hash_password(password)
        self.get(username)

    def hash_password(self, password):
        return hashlib.sha256(str(password).encode('utf-8')).hexdigest()
        # return password

    def verify_password(self):
        if self.password_hash == self.password:
            return True
        else:
            return False

    def get(self, username):
        user_record = self.etcd.get('/appuser/' + username)
        if user_record is not None:
            user = json.loads(user_record[0])

            if user is not None:
                if user['enabled'] is True:
                    self.password_hash = user['password']
                    self.username = user['username']
                    self.locale = user['locale']
                    self.enabled = user['enabled']
                    self.email = user['email']
                    self.role = user['role']
                    return True
        return False

    def set(self):
        user = {}
        user['password'] = self.password_hash
        user['username'] = self.username
        user['locale'] = self.locale
        user['enabled'] = self.enabled
        user['email'] = self.email
        user['role'] = self.role
        self.etcd.put('/appuser/' + self.username, json.dumps(user))

    def is_authenticated(self):
        return self.enabled

    def is_active(self):
        return self.enabled

    def is_anonymous(self):
        return False

    def get_id(self):
        return unicode(self.username)

    def __repr__(self):
        return '<User %r>' % self.username
