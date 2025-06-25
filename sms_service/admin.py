# F:\CRM 2.0\ERP\sms_service\admin.py

from django.contrib import admin
from .models import SMSSettings, SMSTemplate, SMSCampaign, SMSMessage

@admin.register(SMSSettings)
class SMSSettingsAdmin(admin.ModelAdmin):
    """
    Админка для настроек SMS
    """
    list_display = ('name', 'username', 'sender_name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'username', 'sender_name')
    
    fieldsets = (
        ('Основные настройки', {
            'fields': ('name', 'is_active')
        }),
        ('API настройки Rocket SMS', {
            'fields': ('username', 'password', 'api_url')
        }),
        ('Настройки отправки', {
            'fields': ('sender_name',)
        }),
    )

@admin.register(SMSTemplate)
class SMSTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'template_code', 'template_type', 'is_active', 'created_at']
    list_filter = ['template_type', 'is_active', 'created_at']
    search_fields = ['name', 'template_code', 'message_text']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'template_code', 'template_type', 'is_active')
        }),
        ('Текст сообщения', {
            'fields': ('message_text',),
            'description': 'Используйте переменные: {client_name}, {order_number}, {order_type}, {total_amount}, {due_date}'
        }),
        ('Служебная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

@admin.register(SMSCampaign)
class SMSCampaignAdmin(admin.ModelAdmin):
    """
    Админка для SMS рассылок
    """
    list_display = ('name', 'template', 'recipient_type', 'status', 'total_messages', 'sent_messages', 'created_at')
    list_filter = ('recipient_type', 'status', 'created_at', 'created_by')
    search_fields = ('name',)
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'template', 'recipient_type')
        }),
        ('Получатели', {
            'fields': ('manual_phone_numbers',),
            'description': 'Заполняется только для "Ручного списка номеров"'
        }),
        ('Планирование', {
            'fields': ('scheduled_at',)
        }),
        ('Статистика', {
            'fields': ('status', 'total_messages', 'sent_messages', 'failed_messages'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('total_messages', 'sent_messages', 'failed_messages')
    
    def save_model(self, request, obj, form, change):
        """Автоматически ставим создателя рассылки"""
        if not change:  # Если создаём новую рассылку
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SMSMessage)
class SMSMessageAdmin(admin.ModelAdmin):
    """
    Админка для просмотра истории отправленных SMS
    """
    list_display = [
        'id', 
        'phone_number', 
        'recipient_name',
        'status', 
        'sent_at', 
        'cost',
        'sent_by'
    ]
    
    list_filter = [
        'status',
        'sent_at', 
        'sent_by'
    ]
    
    search_fields = [
        'phone_number',
        'recipient_name', 
        'message_text'
    ]
    
    readonly_fields = [
        'rocket_sms_id',
        'api_response',
        'sent_at',
        'created_at'
    ]
    
    # Запрещаем добавление и изменение через админку
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    # Показываем только просмотр
    def has_view_permission(self, request, obj=None):
        return True