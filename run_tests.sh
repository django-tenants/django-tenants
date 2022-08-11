#!/bin/bash

set -e

DATABASE=${DATABASE_HOST:-localhost}
DATABASE_PORT=${DATABASE_PORT:-5432}
echo "Database: $DATABASE"

while ! nc -v -w 1 "$DATABASE" "$DATABASE_PORT" > /dev/null 2>&1 < /dev/null; do
    i=`expr $i + 1`
    if [ $i -ge 50 ]; then
        echo "$(date) - $DATABASE:$DATABASE_PORT still not reachable, giving up"
        exit 1
    fi
    echo "$(date) - waiting for $DATABASE:$DATABASE_PORT..."
    sleep 1
done
echo "postgres connection established"

pushd dts_test_project

EXECUTORS=( standard multiprocessing )

for executor in "${EXECUTORS[@]}"; do
    EXECUTOR=$executor PYTHONWARNINGS=d coverage run manage.py test django_tenants
done
