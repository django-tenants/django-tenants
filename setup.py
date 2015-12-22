#!/usr/bin/env python

from os.path import exists

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

__version__ = "1.1.4"

setup(
    name='django-tenants',
    version=__version__,
    author='Thomas Turner',
    author_email='tom@twt.me.uk',
    packages=[
        'django_tenants',
        'django_tenants.postgresql_backend',
        'django_tenants.management',
        'django_tenants.management.commands',
        'django_tenants.migration_executors',
        'django_tenants.templatetags',
        'django_tenants.test',
        'django_tenants.tests',
    ],
    scripts=[],
    url='https://github.com/tomturner/django-tenants',
    license='MIT',
    description='Tenant support for Django using PostgreSQL schemas.',
    long_description=open('README.rst').read() if exists("README.rst") else "",
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Framework :: Django',
        'Programming Language :: Python',
    ],
    install_requires=[
        'Django >= 1.8.0',
        'psycopg2',
    ],
    zip_safe=False,
)
