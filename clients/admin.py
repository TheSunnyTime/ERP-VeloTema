# CRM 2.0/ERP/clients/admin.py
from django.contrib import admin
from .models import ClientGroup, Client # Импортируем ваши модели

@admin.register(ClientGroup) # Регистрируем модель ClientGroup
class ClientGroupAdmin(admin.ModelAdmin):
    list_display = ('name',) # Показываем только название в списке групп
    search_fields = ('name',) # Позволяем искать по названию группы

@admin.register(Client) # Регистрируем модель Client
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'client_group', 'phone', 'email', 'contact_person', 'created_at') # Поля в списке клиентов
    list_filter = ('client_group', 'created_at') # Фильтры сбоку
    search_fields = ('name', 'phone', 'email', 'contact_person', 'notes') # Поля для поиска
    autocomplete_fields = ('client_group',) # Делает выбор группы удобнее, если групп много
    # fieldsets - можно использовать для группировки полей на странице редактирования, если нужно
    # readonly_fields = ('created_at',) # Если дату создания не нужно редактировать