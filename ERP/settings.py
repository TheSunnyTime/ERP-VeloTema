# CRM 2.0/ERP/ERP/settings.py

from pathlib import Path
import os # Часто используется для BASE_DIR в старых версиях, но с Path можно и без него

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent # Это должно указывать на папку CRM 2.0/ERP/

# QUICK-START DEVELOPMENT SETTINGS
# See https://docs.djangoproject.com/en/stable/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# ЗАМЕНИТЕ ЭТО НА ВАШ УНИКАЛЬНЫЙ КЛЮЧ ИЗ ВАШЕГО settings.py
SECRET_KEY = 'fasasf'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True # Для разработки True, для "боевого" сайта False

ALLOWED_HOSTS = [
    '95.47.60.56',  # Ваш статический IP
    '127.0.0.1',
    'localhost',
]

# Application definition
# F:\CRM 2.0\ERP\ERP\settings.py
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Ваши приложения
    'products.apps.ProductsConfig',
    'orders.apps.OrdersConfig',
    'clients.apps.ClientsConfig',
    'reports.apps.ReportsConfig',
    'cash_register.apps.CashRegisterConfig', # <--- Убедитесь, что эта строка АКТИВНА и правильна
    'utils.apps.UtilsConfig',     # <-- Наше новое приложение
    'salary_management.apps.SalaryManagementConfig'

]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ERP.urls' # Указывает на главный файл urls.py вашего проекта (CRM 2.0/ERP/ERP/urls.py)

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # <--- ИЗМЕНИТЕ ЭТУ СТРОКУ
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

WSGI_APPLICATION = 'ERP.wsgi.application' # Для WSGI серверов

# Database
# https://docs.djangoproject.com/en/stable/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3', # Файл базы данных будет в папке CRM 2.0/ERP/
    }
}

# Password validation
# https://docs.djangoproject.com/en/stable/ref/settings/#auth-password-validators
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
# https://docs.djangoproject.com/en/stable/topics/i18n/
LANGUAGE_CODE = 'ru-ru' # Мы это меняли на русский

TIME_ZONE = 'Europe/Moscow' # Мы это меняли, выберите ваш часовой пояс

USE_I18N = True # Для поддержки интернационализации (переводов)

USE_TZ = True # Для поддержки часовых поясов

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/stable/howto/static-files/
STATIC_URL = 'static/'
# STATIC_ROOT = BASE_DIR / 'staticfiles' # Для команды collectstatic при развертывании
# STATICFILES_DIRS = [ BASE_DIR / "static", ] # Если есть общие статические файлы на уровне проекта

# Default primary key field type
# https://docs.djangoproject.com/en/stable/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'