#encoding: utf-8
require 'etcdv3'
Encoding.default_external = Encoding::UTF_8
conn = Etcdv3.new(endpoints: 'http://localhost:2379')


conn.put('/appuser/admin','{"enabled":true,"locale":"en","password":"8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918","email":"xx@xx.com","username":"admin", "role":"admin"}')

