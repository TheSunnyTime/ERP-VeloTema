from django.apps import AppConfig

class UtilsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'utils'
    verbose_name = 'Сервис' # Так будет называться вкладка в админке