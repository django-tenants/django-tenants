"""
Django settings for dts_test_project project.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.6/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.6/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'cl1)b#c&xmm36z3e(quna-vb@ab#&gpjtdjtpyzh!qn%bc^xxn'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

TEMPLATE_DEBUG = True

ALLOWED_HOSTS = []

# Application definition

SHARED_APPS = (
    'django_tenants',  # mandatory
    'customers',  # you must list the app where your tenant model resides in

    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
)

TENANT_APPS = (
    'dts_test_app',
    'dts_multi_type2',
)

TENANT_APPS_DIR = os.path.join(BASE_DIR, TENANT_APPS[0])
sys.path.insert(0, TENANT_APPS_DIR)
sys.path.insert(0, BASE_DIR)

STATICFILES_DIRS = [
    os.path.join(TENANT_APPS_DIR, "static")
]

MULTITENANT_STATICFILES_DIRS = [
    os.path.join(TENANT_APPS_DIR, "tenants/%s/static")
]

STATICFILES_STORAGE = "django_tenants.staticfiles.storage.TenantStaticFilesStorage"
DEFAULT_FILE_STORAGE = "django_tenants.files.storage.TenantFileSystemStorage"

MULTITENANT_TEMPLATE_DIRS = [
    os.path.join(TENANT_APPS_DIR, "tenants/%s/templates")
]

TENANT_MODEL = "customers.Client"  # app.Model

TENANT_DOMAIN_MODEL = "customers.Domain"  # app.Model

TEST_RUNNER = 'django.test.runner.DiscoverRunner'

TENANT_CACHE_ENABLE = False

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

ROOT_URLCONF = 'dts_test_project.urls'

WSGI_APPLICATION = 'dts_test_project.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.6/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': os.environ.get('DATABASE_DB', 'dts_test_project'),
        'USER': os.environ.get('DATABASE_USER', 'postgres'),
        'PASSWORD': os.environ.get('DATABASE_PASSWORD', 'root'),
        'HOST': os.environ.get('DATABASE_HOST', 'localhost'),
        'PORT': os.environ.get('DATABASE_PORT', 5432),
    }
}

DATABASE_ROUTERS = (
    'django_tenants.routers.TenantSyncRouter',
)

MIDDLEWARE = (
    'django_tenants.middleware.main.TenantMainMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.request',
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.media',
    'django.core.context_processors.static',
    'django.contrib.messages.context_processors.messages',
)

# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = False


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

STATIC_URL = '/static/'

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
