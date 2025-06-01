from django.contrib import admin
from ..models import OrderType # Используем относительный импорт для моделей из orders

@admin.register(OrderType)
class OrderTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)
    ordering = ['name']