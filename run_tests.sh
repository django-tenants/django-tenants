#!/bin/bash

set -e

# Colorful output.
function greenprint {
    echo -e "\033[1;32m[$(date -Isecond)] ${1}\033[0m"
}


DATABASE=${DATABASE_HOST:-127.0.0.1}
DATABASE_PORT=${DATABASE_PORT:-3306}
echo "Database: $DATABASE"


pushd dts_test_project

EXECUTORS=( standard multiprocessing )

for executor in "${EXECUTORS[@]}"; do
    echo "Running tests with executor: $executor"
    EXECUTOR=$executor PYTHONWARNINGS=d coverage run manage.py test -v2 django_tenants
done
