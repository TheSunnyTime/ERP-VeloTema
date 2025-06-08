# suppliers/admin.py
from django.contrib import admin, messages
from django.utils.html import format_html
from .models import Supplier, Supply, SupplyItem # Убедись, что SupplyItem импортирован
from uiconfig.models import SupplyStatusColor

from tasks.models import Task, TaskType, TaskStatus 
from django.contrib.contenttypes.models import ContentType 

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
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
        readonly_fields_list = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            if not request.user.has_perm('suppliers.can_edit_supplier_notes'):
                readonly_fields_list.append('notes')
            if not request.user.has_perm('suppliers.can_change_supplier_status'):
                readonly_fields_list.append('is_active')
        return tuple(set(readonly_fields_list))


class SupplyItemInline(admin.TabularInline):
    model = SupplyItem
    extra = 1
    autocomplete_fields = ['product']
    fields = ('product', 'quantity_received', 'cost_price_per_unit') 
    readonly_fields = ('quantity_remaining_in_batch',) 

    # get_readonly_fields для SupplyItemInline остается без изменений, как в твоем коде


@admin.register(Supply)
class SupplyAdmin(admin.ModelAdmin):
    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        try:
            self.supply_status_colors_map = {
                color.status_key: color.hex_color
                for color in SupplyStatusColor.objects.all()
            }
        except Exception as e:
            print(f"Warning: Could not load supply status colors in SupplyAdmin: {e}")
            self.supply_status_colors_map = {}

    def colored_status(self, obj):
        # ... (твой метод colored_status без изменений) ...
        status_display = obj.get_status_display()
        hex_color = self.supply_status_colors_map.get(obj.status)
        if hex_color:
            text_color = '#ffffff' if int(hex_color[1:3], 16) * 0.299 + int(hex_color[3:5], 16) * 0.587 + int(hex_color[5:7], 16) * 0.114 < 128 else '#000000'
            return format_html(
                '<span style="background-color: {0}; padding: 3px 7px; border-radius: 4px; color: {1};"><strong>{2}</strong></span>',
                hex_color, text_color, status_display
            )
        return status_display
    colored_status.short_description = 'Статус поставки'
    colored_status.admin_order_field = 'status'

    list_display = ('id', 'supplier', 'receipt_date', 'document_number', 'colored_status', 'created_by', 'payment_transaction_created', 'created_at')
    list_filter = ('status', 'supplier', 'receipt_date', 'created_by', 'payment_transaction_created')
    search_fields = ('id', 'supplier__name', 'document_number', 'notes')
    autocomplete_fields = ['supplier', 'created_by']
    inlines = [SupplyItemInline]
    ordering = ('-receipt_date', '-id')
    
    fieldsets = (
        (None, {'fields': ('supplier', 'receipt_date', 'document_number', 'status')}),
        ('Статус оплаты (информация)', {'fields': ('payment_transaction_created',)}),
        ('Дополнительно', {'fields': ('notes',)}),
        ('Информация о записи', {'fields': ('created_by', ('created_at', 'updated_at')), 'classes': ('collapse',)}),
    )
    
    base_readonly_fields = ('created_at', 'updated_at', 'created_by', 'payment_transaction_created')

    def get_readonly_fields(self, request, obj=None):
        # ... (твой метод get_readonly_fields без изменений) ...
        readonly_fields_list = list(self.base_readonly_fields)
        if obj: 
            if obj.status == Supply.STATUS_CANCELLED:
                all_model_fields = [f.name for f in self.model._meta.fields if f.name != self.model._meta.pk.name]
                readonly_fields_list.extend(all_model_fields)
            elif obj.status == Supply.STATUS_RECEIVED:
                if not request.user.is_superuser and not request.user.has_perm('suppliers.can_edit_received_supply'):
                    fields_to_make_readonly = ['supplier', 'receipt_date', 'document_number', 'notes', 'status'] # Добавил status
                    readonly_fields_list.extend(fields_to_make_readonly)
            elif obj.status == Supply.STATUS_PARTIALLY_RECEIVED: # Добавил обработку этого статуса
                 if not request.user.is_superuser and not request.user.has_perm('suppliers.can_edit_received_supply'):
                    fields_to_make_readonly = ['supplier', 'receipt_date', 'document_number', 'notes', 'status'] # Добавил status
                    readonly_fields_list.extend(fields_to_make_readonly)
        return tuple(set(readonly_fields_list))


    def has_change_permission(self, request, obj=None):
        # ... (твой метод has_change_permission без изменений) ...
        if obj and obj.status == Supply.STATUS_CANCELLED:
            return False
        return super().has_change_permission(request, obj)

    def save_model(self, request, obj: Supply, form, change):
        # Запоминаем предыдущий статус из БД для использования в save_related и для логики создания задачи
        if obj.pk: # Если объект уже существует (редактирование)
            try:
                # Сохраняем в атрибут объекта, чтобы передать в save_related
                obj._previous_status_in_db_for_logic = Supply.objects.get(pk=obj.pk).status
            except Supply.DoesNotExist:
                obj._previous_status_in_db_for_logic = None # Или начальный статус, если это важно
        else: # Новый объект
            obj._previous_status_in_db_for_logic = obj.STATUS_DRAFT # Предполагаем, что до первого сохранения он "черновик"

        if not obj.pk: 
            obj.created_by = request.user
        
        # Вызываем Supply.save() (через super().save_model)
        # Supply.save() больше НЕ вызывает update_stock_on_received или _handle_cancellation
        super().save_model(request, obj, form, change) 

        # Логика создания ЗАДАЧИ
        # obj.status теперь содержит новый сохраненный статус
        # previous_status берем из сохраненного _previous_status_in_db_for_logic
        previous_status_for_task = obj._previous_status_in_db_for_logic
        
        needs_task_creation = False
        if obj.status == Supply.STATUS_RECEIVED and not obj.payment_transaction_created:
            if not change: # Новая запись, и статус сразу "Оприходована"
                needs_task_creation = True
            elif change and previous_status_for_task and previous_status_for_task != Supply.STATUS_RECEIVED: # Статус изменился на "Оприходовано"
                needs_task_creation = True
        
        if needs_task_creation:
            # ... (твой код создания задачи без изменений, он использует obj.status и previous_status_for_task) ...
            content_type_supply = ContentType.objects.get_for_model(obj)
            try:
                task_type_supply_payment = TaskType.objects.get(name="Оформить оплату поставки")
                existing_task = Task.objects.filter(content_type=content_type_supply, object_id=obj.pk, task_type=task_type_supply_payment).exclude(status__is_final=True).first()
                if not existing_task:
                    initial_status = TaskStatus.objects.get(name="Новая")
                    assigned_group = task_type_supply_payment.default_visibility_groups.first() if task_type_supply_payment.default_visibility_groups.exists() else None
                    Task.objects.create(
                        title=f"Оформить оплату по поставке №{obj.id}",
                        description=f"Поставщик: {obj.supplier.name}.\nДокумент: {obj.document_number or 'б/н'}.\nДата поставки: {obj.receipt_date.strftime('%d.%m.%Y')}.\nСумма к оплате: {obj.get_total_cost()}",
                        task_type=task_type_supply_payment, status=initial_status, related_object=obj, created_by=request.user, assigned_to_group=assigned_group,
                    )
                    print(f"INFO (SupplyAdmin save_model): Задача на оформление оплаты для поставки #{obj.id} СОЗДАНА.")
                else:
                    print(f"INFO (SupplyAdmin save_model): Активная задача (ID: {existing_task.id}) для поставки #{obj.id} уже существует.")
            except TaskType.DoesNotExist: messages.warning(request, "Тип задачи 'Оформить оплату поставки' не найден."); print(f"ERROR (SupplyAdmin save_model): Тип задачи 'Оформить оплату поставки' не найден для поставки #{obj.id}.")
            except TaskStatus.DoesNotExist: messages.warning(request, "Начальный статус задачи 'Новая' не найден."); print(f"ERROR (SupplyAdmin save_model): Статус задачи 'Новая' не найден для поставки #{obj.id}.")
            except Exception as e: messages.error(request, f"Ошибка при создании задачи на оплату: {e}"); print(f"ERROR (SupplyAdmin save_model) при создании задачи для поставки #{obj.id}: {e}")


    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change) # Сначала сохраняем инлайны (SupplyItem)

        supply_instance = form.instance # supply_instance уже сохранен в save_model
        
        # Получаем предыдущий статус, который мы сохранили в save_model
        previous_status_in_db = getattr(supply_instance, '_previous_status_in_db_for_logic', None)
        
        # Если это новый объект (not change), то previous_status_in_db был STATUS_DRAFT
        # Если это редактирование (change=True), то previous_status_in_db - это статус из БД до всех изменений.
        
        current_status = supply_instance.status # Текущий статус после всех сохранений

        print(f"[SupplyAdmin save_related] Supply ID: {supply_instance.id}, Current Status: {current_status}, Previous DB Status for logic: {previous_status_in_db}")

        # Определяем, нужно ли вызывать update_stock_on_received
        # change - это True, если объект редактируется, False - если создается новый
        process_stock_update = False
        if current_status == Supply.STATUS_RECEIVED:
            if not change: # Новый объект, сразу "Оприходован"
                process_stock_update = True
            elif change and previous_status_in_db != Supply.STATUS_RECEIVED: # Существующий, и статус ИЗМЕНИЛСЯ на "Оприходован"
                process_stock_update = True
        
        # Определяем, нужно ли вызывать _handle_cancellation
        process_cancellation = False
        if current_status == Supply.STATUS_CANCELLED:
            if change and previous_status_in_db != Supply.STATUS_CANCELLED: # Статус ИЗМЕНИЛСЯ на "Отменено"
                process_cancellation = True
            # Отмена нового объекта не должна вызывать _handle_cancellation, так как остатков еще не было.
            # Но если новый объект был сразу "Оприходован", а потом сразу "Отменен" (в одной транзакции сохранения),
            # то _previous_status для _handle_cancellation должен быть RECEIVED.

        if process_stock_update:
            print(f"[SupplyAdmin save_related] Статус '{Supply.STATUS_RECEIVED}'. Вызов update_stock_on_received для поставки #{supply_instance.id}.")
            # Устанавливаем _previous_status для корректной работы update_stock_on_received, если он на него полагается
            # (хотя в текущей версии он не использует _previous_status)
            supply_instance._previous_status = previous_status_in_db # Это статус до того, как он стал RECEIVED
            supply_instance.update_stock_on_received()
            supply_instance._previous_status = current_status # Обновляем для консистентности в памяти

        elif process_cancellation:
            print(f"[SupplyAdmin save_related] Статус '{Supply.STATUS_CANCELLED}'. Вызов _handle_cancellation для поставки #{supply_instance.id}.")
            supply_instance._previous_status = previous_status_in_db # Это статус до того, как он стал CANCELLED
            supply_instance._handle_cancellation()
            supply_instance._previous_status = current_status # Обновляем для консистентности в памяти
        
        # Если _previous_status это атрибут модели и его нужно сохранить в БД (но это не так)
        # if hasattr(supply_instance, '_previous_status_field_in_model'):
        #    if supply_instance._previous_status_field_in_model != current_status:
        #        supply_instance._previous_status_field_in_model = current_status
        #        supply_instance.save(update_fields=['_previous_status_field_in_model'])


    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        # ... (твой метод changeform_view без изменений) ...
        if object_id:
            obj = self.get_object(request, object_id)
            if obj and obj.status == Supply.STATUS_CANCELLED:
                messages.warning(request, "Эта поставка отменена. Редактирование невозможно.")
        return super().changeform_view(request, object_id, form_url, extra_context)