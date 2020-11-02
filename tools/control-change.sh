#!/bin/bash

service etcd start

service postgresql start


if [[ ! -d "/etc/pg_ddm" ]]; then
    /usr/bin/install.sh /home/pg_ddm 1 pg_ddm 1
fi


#su postgres -c 'pgbouncer -d /etc/pgbouncer/pgbouncer.ini'
cd /etc/pg_ddm/
source venv/bin/activate
su pg_ddm -c "cd /etc/pg_ddm/ && source venv/bin/activate && pip install -r admin/requirements.txt"
cd admin

if [[ -f "/etc/pg_ddm/mask_ruby/import.rb" ]]; then

    ruby /etc/pg_ddm/mask_ruby/import.rb
    rm -rf /etc/pg_ddm/mask_ruby/import.rb

fi

if [[ -f "/etc/pg_ddm/mask_ruby/mask.sql" ]]; then
    su postgres -c 'psql -d docker < /etc/pg_ddm/mask_ruby/mask.sql'
    rm /etc/pg_ddm/mask_ruby/mask.sql
fi

su pg_ddm -c 'pg_ddm /etc/pg_ddm/pg_ddm.ini -d -R'

python3 app.py
exit
