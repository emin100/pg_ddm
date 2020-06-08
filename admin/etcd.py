import json

import etcd3
from flask import request, current_app


class Etcd(etcd3.Etcd3Client):
    connection = None

    def __init__(self):
        etcd_settings = current_app.config['ETCD_SETTINGS']
        super().__init__(**etcd_settings)

    def get_x(self, key):
        return self.get(key)

    # def put(self, key, value):
    #     return self.connection.put(key, value)
    #
    # def get(self, key):
    #     return self.connection.get(key)[0]
    #
    # def delete(self, key):
    #     return self.connection.delete(key, )

    def drop(self, key):
        pass

    def get_list(self, key):
        value = self.get(key)[0]
        x = json.loads(value.decode('utf-8'))
        return x

    def search(self, key, json_field=True, search_key=None):
        list_etcd = []
        import re
        if not search_key:
            search_key = request.args.get('search_key')
        for i in self.get_prefix(key, sort_order="ascend", sort_target="key"):
            k = []
            val = json.loads(json.dumps(json.loads(i[0].decode('utf-8')), sort_keys=True))

            if search_key is not None and search_key != '':
                if request.args.get('search_type'):
                    search_type = int(request.args.get('search_type'))
                else:
                    search_type = 2
                search = []
                if search_type in [1, 3]:
                    if json_field is True:
                        search += [key for key in val.values() if re.search(search_key, str(key))]
                    else:
                        search += re.findall(search_key, str(i[0]))
                if search_type in [1, 2]:
                    search += re.findall(search_key, str(i[1].key))
                if len(search) == 0:
                    continue
            if json_field is True:
                k.append(json.loads(json.dumps(json.loads(i[0].decode('utf-8')), sort_keys=True)))
            else:
                k.append(str(i[0]))
            k.append(i[1])
            list_etcd.append(k)
        return list_etcd

    def search_keys(self, key, replace=None):
        list_etcd = []
        if replace is not None:
            key.replace('.', '/')
        for i in self.get_prefix(key):
            list_etcd.append((i[1].key.decode('utf-8').replace('/', '.'))[1:])
        return list_etcd
