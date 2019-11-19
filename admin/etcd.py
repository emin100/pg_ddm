import json

import etcd3


class Etcd(etcd3.Etcd3Client):
    host = None
    port = None
    connection = None

    def __init__(self):
        # env = Settings()
        # env.load_dotenv(".")
        self.host = "0.0.0.0"
        self.port = 2379
        super().__init__(self.host, self.port )

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

    def search(self, key, json_field=True):
        list_etcd = []
        for i in self.get_prefix(key, sort_order="ascend", sort_target="key"):
            k = []
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
