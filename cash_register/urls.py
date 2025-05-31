# F:\CRM 2.0\ERP\cash_register\urls.py
from django.urls import path
from django.contrib import admin # Для admin.site.admin_view
from . import views

app_name = 'cash_register' # Пространство имен для этого приложения

urlpatterns = [
    path('overview-report/', admin.site.admin_view(views.cash_overview_report), name='cash_overview_report'),
    # Сюда можно будет добавить другие URL для cash_register, если понадобятся
]