#!/usr/bin/env python

import io
from os.path import exists

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

__version__ = "1.3.1"

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
        'django_tenants.staticfiles',
    ],
    scripts=[],
    url='https://github.com/tomturner/django-tenants',
    license='MIT',
    description='Tenant support for Django using PostgreSQL schemas.',
    long_description=io.open('README.rst', encoding='utf-8').read() if exists("README.rst") else "",
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'License :: OSI Approved :: MIT License',
        'Framework :: Django',
        'Framework :: Django :: 1.8',
        'Framework :: Django :: 1.9',
        'Framework :: Django :: 1.10',
        'Framework :: Django :: 1.11',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    install_requires=[
        'Django >= 1.8.0,<2.0.0',
        'psycopg2',
    ],
    zip_safe=False,
)
