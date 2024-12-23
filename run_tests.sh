#!/bin/bash

set -e

# Colorful output.
function greenprint {
    echo -e "\033[1;32m[$(date -Isecond)] ${1}\033[0m"
}


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
    echo "Running tests with executor: $executor"
    EXECUTOR=$executor PYTHONWARNINGS=d coverage run manage.py test -v2 django_tenants
done

greenprint "===== START INTEGRATION TESTS ====="

# Make sure we can create a tenant via cloning
greenprint "Create DB"
PYTHONWARNINGS=d python manage.py migrate --noinput

greenprint "Create public schema"
PYTHONWARNINGS=d python manage.py create_tenant --noinput \
    --schema_name public --name "Public tenant" --domain-domain public.example.com --domain-is_primary True

greenprint "Create empty schema - to be used for cloning"
PYTHONWARNINGS=d python manage.py create_tenant --noinput \
    --schema_name empty --name "Cloning template" --domain-domain empty.example.com --domain-is_primary True

greenprint "Execute clone_tenant"
PYTHONWARNINGS=d python manage.py clone_tenant \
    --clone_from empty --clone_tenant_fields False \
    --schema_name a-cloned-tenant --name "A cloned tenant" --description "This tenant was created by cloning" \
    --type type1 --domain-domain a-cloned-tenant.example.com --domain-is_primary True
