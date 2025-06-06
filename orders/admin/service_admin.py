# F:\CRM 2.0\erp\orders\admin\service_admin.py
from django.contrib import admin
from ..models import Service, ServiceCategory # <--- ДОБАВЬ ServiceCategory

@admin.register(ServiceCategory) # <--- НОВАЯ РЕГИСТРАЦИЯ
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)
    ordering = ['name'] # Добавил сортировку для консистентности

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    # ИЗМЕНЕНО: добавлено 'category' и связанные настройки
    list_display = ('name', 'price', 'category') 
    list_filter = ('category',)
    search_fields = ('name', 'category__name') # Поиск по имени категории
    # Чтобы поле "Категория" появилось на форме редактирования услуги:
    fields = ('name', 'price', 'category') 
    # или используй fieldsets, если предпочитаешь:
    # fieldsets = (
    #     (None, {
    #         'fields': ('name', 'price', 'category')
    #     }),
    # )
    autocomplete_fields = ['category'] # Для удобного выбора категории
    ordering = ['name']