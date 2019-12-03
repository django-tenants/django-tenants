from fabric.decorators import task, hosts
from fabric.api import env, run, sudo
from fabtools.postgres import drop_database
from fabtools.vagrant import vagrant
from fabtools.deb import update_index
import fabtools
from fabric.context_managers import cd
from fabtools.require.postgres import create_database

@task
def vagrant():
    env.user = 'vagrant'
    env.hosts = ['127.0.0.1:2020']
    env.passwords = {'vagrant@127.0.0.1:2020': 'vagrant'}
    env.psql_db = 'tenant_tutorial'
    env.psql_user = 'tenant_tutorial'
    env.psql_password = 'qwerty'
    env.backup_path = '/vagrant/database_backup/'
    env.user = 'vagrant'
    env.deploy_user = 'vagrant'
    env.passwords = {'vagrant@127.0.0.1:2020': 'vagrant'}
    env.vagrant = True
    return env.hosts


@task
def provision_vagrant():
    vagrant()
    update_index()
    # fabtools.require.postfix.server('example.com')

    update_requirements()
    create_pg_database()
    django_manage("migrate")
    django_migrate()


@task
def create_superuser():
    django_manage("createsuperuser")


@task
def django_manage(command):
    with cd("/vagrant/examples/tenant_tutorial/"):
        run("python3 manage.py %s" % command)


def update_requirements():
    fabtools.require.deb.packages(['python3',
                                   'python-virtualenv',
                                   'python3-dev',
                                   'python3-setuptools',
                                   'libffi-dev',
                                   'libxslt1-dev',
                                   'python3-pip',
                                   'python3-psycopg2',
                                   'git',
                                   'libboost-python1.*.0',
                                   'pkg-config',
                                   'postgresql-server-dev-10',
                                   'postgresql-contrib',
                                   ])

    sudo("pip3 install django==3.0")


def install_database(name, owner, template='template0', encoding='UTF8', locale='en_US.UTF-8'):
    create_database(name, owner, template=template, encoding=encoding,
                    locale=locale)

@task
def create_pg_database():
    # fabtools.require.postgres.server()
    sudo('service postgresql start', shell=False)

    sudo('psql -c "DROP DATABASE IF EXISTS %s;"' % env.psql_db, user='postgres')
    sudo('psql -c "DROP USER IF EXISTS jmscloud;"', user='postgres')
    sudo('psql -c "CREATE USER %s WITH PASSWORD \'%s\';"' % (env.psql_user, env.psql_password), user='postgres')
    sudo('psql -c "ALTER USER %s WITH SUPERUSER;"' % env.psql_user, user='postgres')

    install_database(env.psql_db, env.psql_user)

    sudo("sed -i 's/all                                     peer/"
         "all                                     md5/g' /etc/postgresql/10/main/pg_hba.conf")
    sudo('service postgresql restart')
    install_database(env.psql_db, env.psql_user)


@task
def reset_database():
    sudo('service postgresql restart')
    try:
        drop_database(env.psql_db)
    except:
        pass
    create_pg_database()
    django_migrate()


def django_migrate():
    django_manage("migrate_schemas")


@task
def create_tenant():
    django_manage("create_tenant")


@task
def runserver():
    django_manage("runserver 0.0.0.0:8088")
