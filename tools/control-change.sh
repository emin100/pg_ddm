#!/bin/bash

service etcd start

service postgresql start

#su postgres -c 'pgbouncer -d /etc/pgbouncer/pgbouncer.ini'
cd /etc/pgbouncer/
source venv/bin/activate
cd admin

if [[ -f "/etc/pgbouncer/mask_ruby/import.rb" ]]; then

    ruby /etc/pgbouncer/mask_ruby/import.rb
    rm -rf /etc/pgbouncer/mask_ruby/import.rb

fi

if [[ -f "/etc/pgbouncer/mask_ruby/mask.sql" ]]; then
    su postgres -c 'psql -d docker < /etc/pgbouncer/mask_ruby/mask.sql'
    rm /etc/pgbouncer/mask_ruby/mask.sql
fi

python3 app.py &
su postgres -c 'pgbouncer /etc/pgbouncer/pgbouncer.ini'
exit
