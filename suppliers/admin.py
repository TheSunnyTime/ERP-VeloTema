# suppliers/admin.py
from django.contrib import admin
from django.utils.html import format_html # <--- ДОБАВЬ ЭТОТ ИМПОРТ
from .models import Supplier, Supply, SupplyItem
from uiconfig.models import SupplyStatusColor # <--- ДОБАВЬ ЭТОТ ИМПОРТ

# ... (SupplierAdmin и SupplyItemInline как были) ...
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    # ... (твой существующий SupplierAdmin, который мы настраивали) ...
    list_display = ('name', 'contact_person_name', 'phone_number', 'email', 'tax_id', 'is_active', 'updated_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('name', 'contact_person_name', 'phone_number', 'email', 'tax_id', 'supplier_manager_name', 'notes')
    fieldsets = (
        (None, {'fields': ('name', 'is_active')}),
        ('Контактная информация поставщика', {'fields': ('contact_person_name', 'phone_number', 'email')}),
        ('Реквизиты', {'fields': ('bank_account', 'tax_id', 'bank_details'), 'classes': ('collapse',)}),
        ('Менеджер у поставщика', {'fields': ('supplier_manager_name', 'supplier_manager_phone'), 'classes': ('collapse',)}),
        ('Дополнительно', {'fields': ('notes',),}),
        ('Даты (служебная информация)', {'fields': (('created_at', 'updated_at'),),'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at', 'updated_at')

    def get_readonly_fields(self, request, obj=None):
        readonly_fields_list = list(super().get_readonly_fields(request, obj)) # Получаем базовый список
        if not request.user.is_superuser:
            if not request.user.has_perm('suppliers.can_edit_supplier_notes'):
                readonly_fields_list.append('notes')
            if not request.user.has_perm('suppliers.can_change_supplier_status'):
                readonly_fields_list.append('is_active')
        return tuple(set(readonly_fields_list))


class SupplyItemInline(admin.TabularInline): # Или StackedInline
    model = SupplyItem
    extra = 1 # Количество пустых форм для добавления
    autocomplete_fields = ['product']
    fields = ('product', 'quantity_received', 'cost_price_per_unit')
    # Можно добавить readonly_fields, если некоторые поля инлайна не должны меняться после создания Supply
    # def get_readonly_fields(self, request, obj=None):
    #     if obj and obj.status == Supply.STATUS_RECEIVED: # obj здесь это Supply
    #         return ['product', 'quantity_received', 'cost_price_per_unit']
    #     return []

@admin.register(Supply)
class SupplyAdmin(admin.ModelAdmin):
    # --- Инициализация для загрузки цветов ---
    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        # Загружаем цвета статусов один раз при инициализации Admin класса
        # Это может вызвать RuntimeWarning при запуске, если uiconfig еще не загружен,
        # но ты решил пока игнорировать это предупреждение.
        try:
            self.supply_status_colors_map = {
                color.status_key: color.hex_color
                for color in SupplyStatusColor.objects.all()
            }
        except Exception as e: # Ловим возможные ошибки, если БД еще не готова (например, при первом запуске)
            print(f"Warning: Could not load supply status colors in SupplyAdmin: {e}")
            self.supply_status_colors_map = {}

    # --- Метод для отображения цветного статуса ---
    def colored_status(self, obj):
        status_display = obj.get_status_display() # Человекочитаемое имя статуса
        hex_color = self.supply_status_colors_map.get(obj.status) # Получаем цвет из карты

        if hex_color:
            # Определяем цвет текста для контраста (простая логика)
            text_color = '#ffffff' if int(hex_color[1:3], 16) * 0.299 + int(hex_color[3:5], 16) * 0.587 + int(hex_color[5:7], 16) * 0.114 < 128 else '#000000'
            return format_html(
                '<span style="background-color: {0}; padding: 3px 7px; border-radius: 4px; color: {1};"><strong>{2}</strong></span>',
                hex_color,
                text_color,
                status_display
            )
        return status_display # Возвращаем обычный текст, если цвет не найден

    colored_status.short_description = 'Статус поставки' # Название колонки
    colored_status.admin_order_field = 'status' # Позволяет сортировку по этому полю

    list_display = ('id', 'supplier', 'receipt_date', 'document_number', 'colored_status', 'created_by', 'created_at') # Заменили 'status' на 'colored_status'
    list_filter = ('status', 'supplier', 'receipt_date', 'created_by')
    search_fields = ('id', 'supplier__name', 'document_number', 'notes')
    autocomplete_fields = ['supplier', 'created_by']
    inlines = [SupplyItemInline]
    # list_editable = ('status',) # РЕКОМЕНДУЮ УБРАТЬ list_editable для статуса, если используем цветной статус
    ordering = ('-receipt_date', '-id')
    
    fieldsets = (
        (None, {'fields': ('supplier', 'receipt_date', 'document_number', 'status')}),
        ('Дополнительно', {'fields': ('notes',)}),
        ('Информация о записи', {
            'fields': ('created_by', ('created_at', 'updated_at')),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at', 'created_by') # created_by лучше сделать readonly после установки

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Логика вызова update_stock_on_received остается в Supply.save() как и было