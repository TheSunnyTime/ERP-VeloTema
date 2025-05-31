# F:\CRM 2.0\ERP\cash_register\apps.py
from django.apps import AppConfig

class CashRegisterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cash_register'
    verbose_name = 'Касса' # Для отображения в админ-панели на русском