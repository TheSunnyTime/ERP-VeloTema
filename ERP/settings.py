# F:\CRM 2.0\ERP\ERP\settings.py

from pathlib import Path
import os
import logging.config # <-- Импорт должен быть вверху

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'fasasf'

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() == 'true'

ALLOWED_HOSTS_STRING = os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost')
ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS_STRING.split(',') if host.strip()]

DATA_UPLOAD_MAX_NUMBER_FIELDS = 20000

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.postgres',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django_extensions',
    'dal',
    'dal_select2',
    'rest_framework',
    'products.apps.ProductsConfig',
    'orders.apps.OrdersConfig',
    'clients.apps.ClientsConfig',
    'cash_register.apps.CashRegisterConfig',
    'utils.apps.UtilsConfig',
    'salary_management.apps.SalaryManagementConfig',
    'reports.apps.ReportsConfig',
    'suppliers.apps.SuppliersConfig',
    'uiconfig.apps.UiconfigConfig',
    'tasks.apps.TasksConfig',
    'grafik.apps.GrafikConfig',
    'sms_service',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ERP.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
            BASE_DIR / 'products' / 'templates',
        ],
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

WSGI_APPLICATION = 'ERP.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / 'staticfiles_collected'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ===================================================================
# БЛОК ЛОГИРОВАНИЯ (ДОЛЖЕН БЫТЬ В КОНЦЕ, ПЕРЕД local_settings)
# ===================================================================

# Создаем папку для логов, если она не существует
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING_CONFIG = None

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json_formatter': {'class': 'logging.Formatter', 'format': '%(message)s'},
        'verbose': {'format': '{levelname} {asctime} {module} {message}', 'style': '{'},
    },
    'handlers': {
        'search_file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': LOGS_DIR / 'search.log', # Используем созданную директорию
            'when': 'H',
            'interval': 1,
            'backupCount': 50,
            'formatter': 'json_formatter',
        },

        'service_search_file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': BASE_DIR / 'logs/service_search.log', # Отдельный файл
            'when': 'H',
            'interval': 4,
            'backupCount': 50,
            'formatter': 'json_formatter',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'products.forms': {
            'handlers': ['search_file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'service_search': {
            'handlers': ['service_search_file', 'console'],
            'level': 'DEBUG',
            'propagate': False, # Чтобы не дублировать логи в другие логгеры
        },
        'django': {
            'handlers': ['console', 'search_file'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}

# Активируем нашу конфигурацию
logging.config.dictConfig(LOGGING)

# ===================================================================
# ИМПОРТ ЛОКАЛЬНЫХ НАСТРОЕК (В САМОМ КОНЦЕ)
# ===================================================================
try:
    from .local_settings import *
except ImportError:
    pass