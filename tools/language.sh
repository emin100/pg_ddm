#!/usr/bin/env bash
PDIR=$( dirname "${BASH_SOURCE[0]}" )/..
cd $PDIR/admin
ls
pybabel extract -F ../conf/babel.cfg -k lazy_gettext -o translations/messages.pot .
pybabel update -i translations/messages.pot -d translations
pybabel compile -d translations