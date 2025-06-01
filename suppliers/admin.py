# suppliers/admin.py
from django.contrib import admin
from .models import Supplier, Supply, SupplyItem

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
    list_display = ('id', 'supplier', 'receipt_date', 'document_number', 'status', 'created_by', 'created_at')
    list_filter = ('status', 'supplier', 'receipt_date', 'created_by')
    search_fields = ('id', 'supplier__name', 'document_number', 'notes')
    autocomplete_fields = ['supplier', 'created_by']
    inlines = [SupplyItemInline]
    list_editable = ('status',) # Осторожно с этим, лучше менять статус через actions или на форме
    ordering = ('-receipt_date', '-id')
    
    fieldsets = (
        (None, {'fields': ('supplier', 'receipt_date', 'document_number', 'status')}),
        ('Дополнительно', {'fields': ('notes',)}),
        ('Информация о записи', {
            'fields': ('created_by', ('created_at', 'updated_at')),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        if not obj.pk: # Если объект создается
            obj.created_by = request.user
        
        old_status = None
        if obj.pk:
            try:
                old_status = Supply.objects.get(pk=obj.pk).status
            except Supply.DoesNotExist:
                pass
        
        super().save_model(request, obj, form, change)
        
        # Логика оприходования после сохранения инлайнов будет в save_related
        # или если статус меняется прямо в save_model, и инлайны уже есть.
        # Но лучше перенести в save_related для надежности.

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Этот метод вызывается ПОСЛЕ сохранения основной модели И ЕЕ ИНЛАЙНОВ.
        # Идеальное место для вызова update_stock_on_received, если статус изменился на "Оприходовано"
        order_instance = form.instance # Это объект Supply
        
        # Проверяем, был ли статус изменен на "Оприходовано" именно сейчас
        # (предполагаем, что self._previous_status тут не сработает так, как для Order)
        # Поэтому, если статус "Оприходовано", просто вызываем.
        # Для идемпотентности update_stock_on_received должен сам проверять, не были ли остатки уже обновлены по этой поставке.
        # Либо нам нужна более сложная логика отслеживания "первого" перехода в "Оприходовано".
        
        # Простой вариант: если статус "Оприходовано", пытаемся обновить.
        # Внутри update_stock_on_received можно добавить проверку, чтобы не делать это дважды.
        # Однако, это вызовется каждый раз при сохранении Supply со статусом "Оприходовано".
        # Это не идеально. Лучше отслеживать изменение статуса.

        # Пока что оставим вызов update_stock_on_received в Supply.save(), 
        # но с пониманием, что он должен быть идемпотентным или вызываться более хитро.
        # Для админки более правильно было бы сделать "действие" (action) "Оприходовать выбранные поставки".
        # Или перенести логику из Supply.save() сюда, если статус изменился.

        # Для начала, оставим логику в Supply.save(), она сработает после super().save_model()
        # если статус там уже был установлен.
        # Но если статус меняется через list_editable или действие, то Supply.save() может не быть идеальным местом.
        # Для list_editable, save() модели вызывается.

        # Если мы хотим явный вызов после того, как все (включая инлайны) сохранено и статус стал "Оприходовано":
        # if order_instance.status == Supply.STATUS_RECEIVED:
        #     # Здесь нужно проверить, был ли он другим до этого сохранения
        #     # Это сложнее без _previous_status как в Order
        #     # Проще всего сделать так, чтобы update_stock_on_received была безопасна для повторного вызова
        #     # или выполнялась только если есть флаг "еще не оприходовано".
        #     order_instance.update_stock_on_received() # Вызовем еще раз на всякий случай, если инлайны только что сохранились
        pass # Логика оприходования пока в Supply.save() или будет пересмотрена