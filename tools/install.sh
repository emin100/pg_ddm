#!/usr/bin/env bash

cd $1


PgBouncerPath=/etc/pgbouncer
PgDdmPath=$1/pg_ddm


#Download source codes
if [[ -f "${PgDdmPath}/Dockerfile" ]];
then
    cd ${PgDdmPath}
    git pull
else
    git clone https://github.com/emin100/pg_ddm.git --recursive
    cd ${PgDdmPath}
fi

#git submodule init
#git submodule update


#Copy patches and other files inside to pgbouncer
cp -R ${PgDdmPath}/pgbouncer_diff/* ${PgDdmPath}/pgbouncer/
cd ${PgDdmPath}/pgbouncer
git apply pg_ddm.patch


#git submodule init
#git submodule update
./autogen.sh
./configure
make

#mv pgbouncer ../pg_ddm

cd ${PgDdmPath}/pg_query
gem build pg_query.gemspec
#gem install hashie etcdv3
#gem install pg_query*.gem


cd ${PgDdmPath}

if [[ -d  "$PgBouncerPath" ]]
then
    cp conf/pgbouncer.ini conf/pg_ddm.ini conf/userlist.txt ${PgBouncerPath}/
    cp -r mask_ruby admin ${PgBouncerPath}/
fi


cd ${PgBouncerPath}

if [[ ! -f "${PgBouncerPath}/venv/bin/activate" ]]; then
    virtualenv --python=python3 venv
fi



source venv/bin/activate
cd ${PgBouncerPath}/admin
pip install -r requirements.txt