# ERP/suppliers/urls.py
from django.urls import path
from . import views # Убедись, что views.py существует в suppliers и импортирует нужную view

app_name = 'suppliers' # Имя пространства имен для URL-адресов этого приложения

urlpatterns = [
    # ... возможно, другие URL для suppliers, если они есть ...
    
    # Раскомментируй или добавь этот путь для импорта позиций поставки
    path('supply/import-items/', views.import_supply_items_from_csv_view, name='import_supply_items_csv'),
]