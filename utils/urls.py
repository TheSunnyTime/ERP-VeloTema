# F:\CRM 2.0\ERP\utils\urls.py
from django.urls import path
from django.contrib import admin # Для admin.site.admin_view
from . import views # Импортируем views из текущего приложения utils

app_name = 'utils' # Пространство имен для URL-адресов этого приложения

urlpatterns = [
    # URL для импорта CSV (у вас уже должен быть)
    path(
        'import-product-csv/', 
        admin.site.admin_view(views.product_csv_import_view), 
        name='import_product_csv'
    ),

    # ----- НОВЫЙ URL ДЛЯ ГЕНЕРАЦИИ ДОКУМЕНТОВ -----
    path(
        'generate-document/template<int:template_id>/object<int:object_id>/', 
        admin.site.admin_view(views.generate_document_view), 
        name='generate_document'
    ),
 # --- НОВЫЙ URL ДЛЯ ОТЧЕТА ПО ЗАРПЛАТЕ СОТРУДНИКА ---
     path(
        'my-salary-report/',
        admin.site.admin_view(views.employee_salary_report_view),
        name='my_salary_report'
    ),
    # --- НОВЫЙ URL ДЛЯ API БАЛАНСА СОТРУДНИКА ---
    path(
        'api/get-employee-balance/<int:employee_id>/',
        views.get_employee_balance_api, # Не оборачиваем в admin_view, т.к. это API
        name='api_get_employee_balance'
    ),
    # ---------------------------------------------
]