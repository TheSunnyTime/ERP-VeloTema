from django.contrib import admin
from ..models import Service # Используем относительный импорт

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'price')
    search_fields = ('name',)
    ordering = ['name']