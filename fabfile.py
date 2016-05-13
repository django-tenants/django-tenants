from fabric.decorators import task, hosts
from fabric.api import env, run, sudo
from fabtools.postgres import drop_database
from fabtools.vagrant import vagrant
from fabtools.deb import update_index
import fabtools
from fabric.context_managers import cd


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
    fabtools.require.postfix.server('example.com')
    create_pg_database()
    update_requirements()
    django_manage("migrate")
    django_migrate()


@task
def create_superuser():
    django_manage("createsuperuser")


@task
def django_manage(command):
    with cd("/vagrant/examples/tenant_tutorial/"):
        run("python manage.py %s" % command)


def update_requirements():
    fabtools.require.deb.packages(['python2.7',
                                   'python-virtualenv',
                                   'python-dev',
                                   'python-pip',
                                   'pkg-config',
                                   'postgresql-server-dev-9.3'])

    sudo("pip install psycopg2==2.6.1 django==1.9")


@task
def create_pg_database():
    fabtools.require.postgres.server()
    fabtools.require.postgres.user(env.psql_user, env.psql_password, createdb=True)
    fabtools.require.postgres.database(env.psql_db, env.psql_user)

    sudo("sed -i 's/all                                     peer/"
         "all                                     md5/g' /etc/postgresql/9.3/main/pg_hba.conf")
    sudo('service postgresql restart')


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
