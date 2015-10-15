#!/bin/bash

set -e

pushd dts_test_project

EXECUTORS=( standard multiprocessing )

for executor in "${EXECUTORS[@]}"; do
    EXECUTOR=$executor python manage.py test django_tenants.tests
done
