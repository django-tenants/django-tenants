#!/bin/bash

set -e

# Colorful output.
function greenprint {
    echo -e "\033[1;32m[$(date -Isecond)] ${1}\033[0m"
}


pushd dts_test_project

EXECUTORS=( standard multiprocessing )

for executor in "${EXECUTORS[@]}"; do
    echo "Running tests with executor: $executor"
    EXECUTOR=$executor PYTHONWARNINGS=d coverage run manage.py test -v2 django_tenants
done

greenprint "===== START INTEGRATION TESTS ====="

# Create MySQL database if it doesn't exist
greenprint "Ensure MySQL database 'dts_test_project' exists"
mysql -h 127.0.0.1 -u root -e "CREATE DATABASE IF NOT EXISTS dts_test_project;"

# Make sure we can create a tenant via cloning
greenprint "Create DB"
PYTHONWARNINGS=d python manage.py migrate --noinput

greenprint "Create public schema"
PYTHONWARNINGS=d python manage.py create_tenant --noinput \
    --schema_name dts_test_project1 --name "Public tenant" --domain-domain public.example.com --domain-is_primary True

greenprint "Create empty schema - to be used for cloning"
PYTHONWARNINGS=d python manage.py create_tenant --noinput \
    --schema_name empty --name "Cloning template" --domain-domain empty.example.com --domain-is_primary True
