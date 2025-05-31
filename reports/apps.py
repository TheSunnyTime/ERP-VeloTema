# CRM 2.0/ERP/reports/apps.py
from django.apps import AppConfig

class ReportsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reports'
    verbose_name = 'Отчеты'  # <--- ДОБАВЬТЕ ЭТУ СТРОКУ