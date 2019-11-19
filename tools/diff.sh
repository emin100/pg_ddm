#!/bin/bash
PDIR=$( dirname "${BASH_SOURCE[0]}" )
PGBOUNCER=$( dirname "${BASH_SOURCE[0]}" )/../pgbouncer
cd $PGBOUNCER
git diff > pg_ddm.patch
for i in $( git status --porcelain  | grep '^??'  | cut -c4- ); do
    cp $i ../pgbouncer_diff/$i
    echo "$i-../pgbouncer_diff/$i"
done