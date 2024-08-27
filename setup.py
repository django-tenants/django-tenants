 #!/usr/bin/env python

import io
from os.path import exists

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

__version__ = "3.7.0"

setup(
    name='django-tenants',
    version=__version__,
    author='Thomas Turner',
    author_email='tom@twt.me.uk',
    packages=[
        'django_tenants',
        'django_tenants.files',
        'django_tenants.postgresql_backend',
        'django_tenants.management',
        'django_tenants.management.commands',
        'django_tenants.migration_executors',
        'django_tenants.template',
        'django_tenants.template.loaders',
        'django_tenants.templatetags',
        'django_tenants.test',
        'django_tenants.tests',
        'django_tenants.staticfiles',
        'django_tenants.middleware',
    ],
    include_package_data=True,
    scripts=[],
    url='https://github.com/django-tenants/django-tenants',
    license='MIT',
    description='Tenant support for Django using PostgreSQL schemas.',
    long_description=io.open('README.rst', encoding='utf-8').read() if exists("README.rst") else "",
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'License :: OSI Approved :: MIT License',
        'Framework :: Django',
        'Framework :: Django :: 4.2',
        'Framework :: Django :: 5.0',
        'Framework :: Django :: 5.1',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    install_requires=[
        'Django >=2.1,<5.2',
    ],
    zip_safe=False,
)
