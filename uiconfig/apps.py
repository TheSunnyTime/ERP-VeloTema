# uiconfig/apps.py
from django.apps import AppConfig

class UiconfigConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'uiconfig'
    verbose_name = 'Настройки интерфейса' # Можешь добавить это для лучшего отображения в админке