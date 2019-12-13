#!/bin/bash
PDIR=$( dirname "${BASH_SOURCE[0]}" )
PGBOUNCER=$( dirname "${BASH_SOURCE[0]}" )/../pgbouncer
cd $PGBOUNCER

make clean
make distclean

rm -rf $(find . -maxdepth 1 -type f -name "config.*" ! -name "*.mak.in") install-sh configure doc/pgddm.*


git diff > pg_ddm.patch
for i in $( git status --porcelain  | grep '^??'  | cut -c4- ); do
    cp $i ../pgbouncer_diff/$i
    echo "$i-../pgbouncer_diff/$i"
done