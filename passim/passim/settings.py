"""
Django settings for passim project.

Generated by 'django-admin startproject' using Django 1.9.1.

For more information on this file, see
https://docs.djangoproject.com/en/1.9/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.9/ref/settings/
"""

import os
import posixpath
import socket
import sys
from django.contrib import admin

hst = socket.gethostbyname(socket.gethostname())
bUseTunnel = False

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_NAME = os.path.basename(BASE_DIR)
WRITABLE_DIR = os.path.abspath(os.path.join(BASE_DIR, "../../writable/database/"))

# print("Writable dir = [{}]".format(WRITABLE_DIR))

if "RU-passim\\writable" in WRITABLE_DIR:
    # Need another string
    WRITABLE_DIR = os.path.abspath(os.path.join(BASE_DIR, "../../../writable/database/"))
elif "/applejack" in BASE_DIR:
    WRITABLE_DIR = os.path.abspath(os.path.join(BASE_DIR, "../../writable/passim/database/"))

MEDIA_DIR = os.path.abspath(os.path.join(WRITABLE_DIR, "../media/"))

APP_PREFIX = ""
USE_REDIS = False
ADMIN_SITE_URL = ""
if "d:" in WRITABLE_DIR or "D:" in WRITABLE_DIR or "c:" in WRITABLE_DIR or "C:" in WRITABLE_DIR or bUseTunnel:
    APP_PREFIX = ""
    # admin.site.site_url = '/'
    ADMIN_SITE_URL = "/"
    # Specific differentiation
    if "d:" in WRITABLE_DIR or "D:" in WRITABLE_DIR:
        USE_REDIS = True
elif "131.174" in hst:
    # Configuration within the Radboud University environment (AppleJack)
    APP_PREFIX = ""             # Was: "passim/"
    #admin.site.site_url = '/'   # Was: '/passim'
    ADMIN_SITE_URL = "/"
    USE_REDIS = True
elif "/var/www" in WRITABLE_DIR:
    # New configuration of http://corpus-studio-web.cttnww-meertens.surf-hosted.nl/passim
    APP_PREFIX = "passim/"
    #admin.site.site_url = '/passim'
    ADMIN_SITE_URL = "/passim"
    USE_REDIS = True
else:
    APP_PREFIX = "dd/"
    #admin.site.site_url = '/dd'
    ADMIN_SITE_URL = "/dd"

# NOTE: change admin.site.site_url in admin.py if needed

# FORCE_SCRIPT_NAME = admin.site.site_url

DATA_UPLOAD_MAX_NUMBER_FIELDS = None

   

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.9/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '561c5400-4ebf-4e45-a2ec-12d856638e45'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', 'applejack.science.ru.nl', 'passim.rich.ru.nl', 'testserver' ]

# Caching
if USE_REDIS:
    CACHES = {"default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": "redis://127.0.0.1:7779/1",
                "OPTIONS": { "CLIENT_CLASS": "django_redis.client.DefaultClient", }
                },
                "select2": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": "redis://127.0.0.1:7779/2",
                "OPTIONS": { "CLIENT_CLASS": "django_redis.client.DefaultClient", }
                }
            }
    # Set the cache backend to select2
    SELECT2_CACHE_BACKEND = 'select2'

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    'reportlab',
    # Add your apps here to enable them
    'django_select2',
    'passim.basic',
    'passim.bible',
    'passim.reader',
    'passim.seeker',
    'passim.dct',
    'passim.enrich'
]

# MIDDLEWARE_CLASSES = [
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # 'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'passim.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'passim/templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'passim.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(WRITABLE_DIR, 'passim.db'),
        'TEST': {
            'NAME': os.path.join(WRITABLE_DIR, 'passim-test.db'),
            }
    }
}


# Password validation
# https://docs.djangoproject.com/en/1.9/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.9/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Europe/Amsterdam'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/

STATIC_URL = '/static/'
if ("/var/www" in WRITABLE_DIR and not bUseTunnel):
    STATIC_URL = "/" + APP_PREFIX + "static/"

STATIC_ROOT = os.path.abspath(os.path.join("/", posixpath.join(*(BASE_DIR.split(os.path.sep) + ['static']))))
