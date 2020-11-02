#!/usr/bin/env bash

cd $1


PgDdmPath=/etc/pg_ddm
PgDdmSourcePath=$1/pg_ddm


#Download source codes
if [[ -f "${PgDdmSourcePath}/Dockerfile" ]];
then
    cd ${PgDdmSourcePath}
    git pull
    cd pgbouncer
    git stash
    git stash drop

else
    git clone https://github.com/emin100/pg_ddm.git --recursive
    cd ${PgDdmSourcePath}
fi

USERNAME=$3

if [ "$USERNAME" == "" ];
then
    USERNAME=`whoami`
fi

NEWINSTALL=$4

if [ "$NEWINSTALL" == "" ];
then
    NEWINSTALL=0
fi

MAKEX=$2

if [ "$MAKEX" == "" ];
then
    MAKEX=0
fi

cd  ${PgDdmSourcePath}/pgbouncer

if [ "$MAKEX" == "1" ];
then

    make clean
    make distclean

    rm -rf $(find . -maxdepth 1 -type f -name "config.*" ! -name "*.mak.in") install-sh configure doc/pg_ddm.*

    ./autogen.sh
    ./configure

fi

#Copy patches and other files inside to pgbouncer
cp -R ${PgDdmSourcePath}/pgbouncer_diff/* ${PgDdmSourcePath}/pgbouncer/
git apply pg_ddm.patch

make -j4
make install


gem install pg_ddm_sql_modifier

cd $PgDdmSourcePath

mkdir -p $PgDdmPath
cp -R admin mask_ruby $PgDdmPath/

if [ ! -f $PgDdmPath/pg_ddm.ini ] || [ $NEWINSTALL -eq 1 ];
then
    cp -R  $PgDdmSourcePath/pgbouncer/etc/pg_ddm.ini  $PgDdmPath/
    sed -i 's/\[databases\]/\[databases\]\ndocker = host=localhost dbname=docker search_path=public/g' /etc/pg_ddm/pg_ddm.ini
    sed -i 's/listen_addr = 127.0.0.1/listen_addr = */g' /etc/pg_ddm/pg_ddm.ini
    echo '"docker"  "md5fd33bb5f0e7607674a50a658b5bbfa2e"' >  $PgDdmPath/userlist.txt
fi
mkdir -p /var/log/pg_ddm
mkdir -p /var/run/pg_ddm

cd ${PgDdmPath}

if [[ ! -f "${PgDdmPath}/venv/bin/activate" ]]; then
    virtualenv --python=python3 venv
fi



source venv/bin/activate
cd ${PgDdmPath}/admin
pip install -r requirements.txt



chown -R $USERNAME:$USERNAME /var/log/pg_ddm /var/run/pg_ddm $PgDdmPath

