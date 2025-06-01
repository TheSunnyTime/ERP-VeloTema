from django.apps import AppConfig


class SuppliersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'suppliers' # Внутреннее имя приложения остается 'suppliers'
    verbose_name = 'Поставки' # <--- ВОТ ЭТО ИЗМЕНЕНИЕ для отображения в админке