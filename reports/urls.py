# CRM 2.0/ERP/reports/urls.py
from django.urls import path
from . import views
from django.contrib import admin # Этот импорт нужен для admin.site.admin_view

app_name = 'reports'  # <--- УБЕДИТЕСЬ, ЧТО ЭТА СТРОКА ЕСТЬ И НАПИСАНА ПРАВИЛЬНО

urlpatterns = [
    path('stock-summary/', admin.site.admin_view(views.stock_summary_report), name='stock_summary_report'),
    path( # <--- Убедись, что этот path раскомментирован
        'all-employees-salary/', 
        admin.site.admin_view(views.all_employees_salary_report_view),
        name='all_employees_salary_report'
    ),
]