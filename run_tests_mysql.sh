#!/bin/bash

set -e

function greenprint {
    echo -e "\033[1;32m[$(date -Isecond)] ${1}\033[0m"
}

DATABASE=${DATABASE_HOST:-localhost}
DATABASE_PORT=${DATABASE_PORT:-3306}
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
echo "mysql connection established"

export DATABASE_ENGINE=django_tenants.mysql_backend

pushd dts_test_project

EXECUTORS=( standard multiprocessing )

for executor in "${EXECUTORS[@]}"; do
    echo "Running MySQL-specific tests with executor: $executor"
    EXECUTOR=$executor PYTHONWARNINGS=d coverage run manage.py test -v2 django_tenants.tests.test_mysql_backend
done

greenprint "===== START INTEGRATION TESTS ====="

greenprint "Create public schema"
PYTHONWARNINGS=d python manage.py migrate --noinput
PYTHONWARNINGS=d python manage.py create_tenant --noinput \
    --schema_name public --name "Public tenant" --domain-domain public.example.com --domain-is_primary True

greenprint "Create a tenant"
PYTHONWARNINGS=d python manage.py create_tenant --noinput \
    --schema_name a-mysql-tenant --name "A MySQL tenant" --domain-domain a-mysql-tenant.example.com --domain-is_primary True

greenprint "Confirm clone_tenant is rejected on MySQL"
if PYTHONWARNINGS=d python manage.py clone_tenant \
    --clone_from a-mysql-tenant --clone_tenant_fields False \
    --schema_name a-cloned-tenant --name "Should fail" --domain-domain a-cloned-tenant.example.com --domain-is_primary True; then
    echo "clone_tenant should have failed on the MySQL backend but did not"
    exit 1
fi
greenprint "clone_tenant correctly rejected"
