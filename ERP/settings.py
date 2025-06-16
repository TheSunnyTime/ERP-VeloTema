# ERP/settings.py (или F:\CRM 2.0\ERP\ERP\settings.py)

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent # Это должно указывать на папку F:\CRM 2.0\erp\ (или F:\CRM 2.0\erp_live\)

# SECURITY WARNING: keep the secret key used in production secret!
# Этот ключ будет использоваться по умолчанию.
# Для "рабочей" среды (erp_live) ОБЯЗАТЕЛЬНО переопредели его на новый и сложный
# в файле erp_live/ERP/local_settings.py
SECRET_KEY = 'fasasf' # ЗАМЕНИ ЭТО НА СВОЙ СЛОЖНЫЙ КЛЮЧ ДЛЯ РАЗРАБОТКИ, ЕСЛИ ХОЧЕШЬ

# По умолчанию DEBUG = False (более безопасно).
# В erp/ERP/local_settings.py для разработки мы установим DEBUG = True.
# В erp_live/ERP/local_settings.py DEBUG должен остаться False или быть явно установлен в False.
DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() == 'true'

# ALLOWED_HOSTS по умолчанию. Будет переопределено в local_settings.py для каждой среды.
# Если DJANGO_ALLOWED_HOSTS не установлена, разрешает только стандартные хосты для разработки.
ALLOWED_HOSTS_STRING = os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost')
ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS_STRING.split(',') if host.strip()]


DATA_UPLOAD_MAX_NUMBER_FIELDS = 20000 # Или другое значение, больше 1000
                                      # Подбери значение, достаточное для твоих нужд,
                                      # но не слишком большое без необходимости.

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles', # Перенес сюда, к остальным django.contrib
    'django.contrib.humanize', # Добавил, если вдруг понадобится для форматирования чисел/дат
    'django_extensions',
    'dal',
    'dal_select2',

    # Ваши кастомные приложения
    'products.apps.ProductsConfig',
    'orders.apps.OrdersConfig',
    'clients.apps.ClientsConfig',
    'cash_register.apps.CashRegisterConfig',
    'utils.apps.UtilsConfig',
    'salary_management.apps.SalaryManagementConfig',
    'reports.apps.ReportsConfig',
    'suppliers.apps.SuppliersConfig', # Ты указал его раньше staticfiles, перенес к остальным кастомным
    'uiconfig.apps.UiconfigConfig',   # <-- ДОБАВЛЕНО НАШЕ НОВОЕ ПРИЛОЖЕНИЕ
    'tasks.apps.TasksConfig', # или просто 'tasks'
    'grafik.apps.GrafikConfig', # ИЗМЕНИТЬ ЗДЕСЬ
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

ROOT_URLCONF = 'ERP.urls' # Убедись, что имя проекта ERP совпадает с именем папки с settings.py

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Путь к общим шаблонам на уровне проекта (например, templates/admin/base_site.html)
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True, # Искать шаблоны также в папках templates внутри приложений
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
        'NAME': BASE_DIR / 'db.sqlite3', # Файл db.sqlite3 будет в корне текущей копии проекта
    }
}

# Password validation
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
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow' # Убедись, что это твой актуальный часовой пояс
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

# STATICFILES_DIRS - для статики, не привязанной к конкретному приложению,
# а лежащей в общей папке static на уровне проекта (рядом с manage.py)
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# STATIC_ROOT - папка, куда будет собираться вся статика командой collectstatic
# Обычно используется только для DEBUG = False.
# Ее можно определить здесь или переопределить в local_settings.py для "рабочей" среды.
# Пример: STATIC_ROOT = BASE_DIR / 'staticfiles_collected'

# MEDIA_URL и MEDIA_ROOT - для файлов, загружаемых пользователями (если они есть)
# MEDIA_URL = '/media/'
# MEDIA_ROOT = BASE_DIR / 'media'


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --- ИМПОРТ ЛОКАЛЬНЫХ НАСТРОЕК ---
# Этот блок должен быть в САМОМ КОНЦЕ файла
try:
    from .local_settings import *
    # Для отладки при первом запуске можно добавить:
    # print(f"[{BASE_DIR}] Successfully imported local_settings.py")
except ImportError:
    # Для отладки при первом запуске можно добавить:
    # print(f"[{BASE_DIR}] local_settings.py not found or could not be imported. Using default settings from main settings.py.")
    pass
# --- КОНЕЦ БЛОКА ИМПОРТА ---