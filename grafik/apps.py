from django.apps import AppConfig


class GrafikConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'grafik'
    verbose_name = "График" # Вот это важно!
