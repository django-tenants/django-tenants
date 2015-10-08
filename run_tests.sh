#!/bin/bash

pushd dts_test_project

EXECUTOR=standard python manage.py test django_tenants.tests

EXECUTOR=multiprocessing python manage.py test django_tenants.tests
