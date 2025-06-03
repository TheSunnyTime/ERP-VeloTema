# CRM 2.0/ERP/reports/urls.py
from django.urls import path
from . import views
from django.contrib import admin # Этот импорт нужен для admin.site.admin_view

app_name = 'reports'

urlpatterns = [
    path('stock-summary/', admin.site.admin_view(views.stock_summary_report), name='stock_summary_report'),
    path(
        'all-employees-salary/',
        admin.site.admin_view(views.all_employees_salary_report_view),
        name='all_employees_salary_report'
    ),
    # Добавляем новый URL для отчета по расходам
    path(
        'expenses/', # URL будет /reports-custom/expenses/ (или как ты настроил в основном urls.py)
        admin.site.admin_view(views.expense_report_view), # Оборачиваем в admin_view
        name='expense_report' # Имя для использования в reverse()
    ),
]