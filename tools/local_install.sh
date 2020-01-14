#!/usr/bin/env bash

PDIR=$( dirname "${BASH_SOURCE[0]}" )

USERNAME=$2

if [ "$USERNAME" == "" ];
then
    USERNAME=`whoami`
fi

NEWINSTALL=$3

if [ "$NEWINSTALL" == "" ];
then
    NEWINSTALL=0
fi

MAKEX=$1

if [ "$MAKEX" == "" ];
then
    MAKEX=0
fi

cd $PDIR/../pgbouncer

if [ "$MAKEX" == "1" ];
then

    make clean
    make distclean

    rm -rf $(find . -maxdepth 1 -type f -name "config.*" ! -name "*.mak.in") install-sh configure doc/pg_ddm.*

    ./autogen.sh
    ./configure
    make -j4
    sudo make install

fi


DDMPATH="/etc/pg_ddm"

cd ..

sudo mkdir -p $DDMPATH
sudo cp -R admin mask_ruby $DDMPATH/

if [ ! -f $DDMPATH/pg_ddm.ini ] || [ $NEWINSTALL -eq 1 ];
then
    sudo cp -R  pgbouncer/etc/pg_ddm.ini pgbouncer/etc/userlist.txt  $DDMPATH/
fi


sudo mkdir -p /var/log/pg_ddm
sudo mkdir -p /var/run/pg_ddm


sudo chown -R $USERNAME:$USERNAME /var/log/pg_ddm /var/run/pg_ddm $DDMPATH

