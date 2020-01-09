#!/bin/bash

set -e

DATABASE=${DATABASE_HOST:-localhost}
echo "Database: $DATABASE"

while ! nc -v -w 1 "$DATABASE" "5432" > /dev/null 2>&1 < /dev/null; do
    i=`expr $i + 1`
    if [ $i -ge 50 ]; then
        echo "$(date) - $DATABASE:5432 still not reachable, giving up"
        exit 1
    fi
    echo "$(date) - waiting for $DATABASE:5432..."
    sleep 1
done
echo "postgres connection established"

pushd dts_test_project

EXECUTORS=( standard, )

for executor in "${EXECUTORS[@]}"; do
    EXECUTOR=$executor python -Wd manage.py test django_tenants.tests
done
