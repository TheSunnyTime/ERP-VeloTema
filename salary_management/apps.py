# F:\CRM 2.0\ERP\salary_management\apps.py
from django.apps import AppConfig

class SalaryManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'salary_management'
    verbose_name = 'Зарплаты' # Название для раздела в админке