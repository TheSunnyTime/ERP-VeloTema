from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils import timezone # Для работы с timezone.now()
from datetime import timedelta # Для правила 24 часов
from decimal import Decimal # Убедимся, что Decimal импортирован

# Импортируем модели и кастомное исключение
from .models import Supplier, Supply, SupplyItem, CannotCancelError 
from uiconfig.models import SupplyStatusColor # Если используется для цветов статусов

# Для создания задач (если логика остается)
from tasks.models import Task, TaskType, TaskStatus 
from django.contrib.contenttypes.models import ContentType 

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    # Код SupplierAdmin остается без изменений из твоего предыдущего варианта
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
    # ИЗМЕНЕНО: Добавлено 'line_total' в fields
    fields = ('product', 'quantity_received', 'cost_price_per_unit', 'line_total', 'quantity_remaining_in_batch')
    # ИЗМЕНЕНО: Добавлено 'line_total' к base_readonly_fields
    base_readonly_fields = ('quantity_remaining_in_batch', 'line_total')

    def line_total(self, obj):
        """Рассчитывает сумму по строке: количество * себестоимость."""
        if obj.pk and obj.quantity_received is not None and obj.cost_price_per_unit is not None:
            return (obj.quantity_received * obj.cost_price_per_unit).quantize(Decimal('0.01'))
        return Decimal('0.00')
    line_total.short_description = "Сумма по строке"

    def get_readonly_fields(self, request, obj=None):
        # Используем копию base_readonly_fields, чтобы не изменять исходный кортеж класса
        current_readonly = list(self.base_readonly_fields)
        if hasattr(self, 'readonly_fields_set_by_parent'):
            # Если родительский админ устанавливает readonly поля,
            # добавляем к ним наши базовые readonly поля (включая line_total),
            # чтобы они не стали редактируемыми.
            # Используем set для избежания дубликатов.
            return tuple(set(list(self.readonly_fields_set_by_parent) + current_readonly))
        return tuple(current_readonly)


@admin.register(Supply)
class SupplyAdmin(admin.ModelAdmin):
    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        try:
            self.supply_status_colors_map = {
                color.status_key: color.hex_color
                for color in SupplyStatusColor.objects.all()
            }
        except Exception as e: # noqa
            self.supply_status_colors_map = {}

    def colored_status(self, obj):
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

    list_display = (
        'id', 'supplier',
        'expected_delivery_date',
        'receipt_date',
        'colored_status',
        'received_at',
        'created_by',
        'payment_transaction_created',
        'created_at'
    )
    list_filter = ('status', 'supplier', 'receipt_date', 'expected_delivery_date', 'created_by', 'payment_transaction_created')
    search_fields = ('id', 'supplier__name', 'document_number', 'notes')
    autocomplete_fields = ['supplier', 'created_by']
    inlines = [SupplyItemInline]
    ordering = ('-receipt_date', '-id')

    # ИЗМЕНЕНО: Добавлено 'display_total_supply_cost' в fieldsets
    fieldsets = (
        (None, {
            'fields': ('supplier', 'expected_delivery_date', 'receipt_date', 'document_number', 'status', 'display_total_supply_cost')
        }),
        ('Информация об оприходовании и оплате', {
            'fields': ('received_at', 'payment_transaction_created',),
            'classes': ('collapse',),
        }),
        ('Дополнительно', {'fields': ('notes',)}),
        ('Информация о записи', {
            'fields': ('created_by', ('created_at', 'updated_at')),
            'classes': ('collapse',)
        }),
    )

    # ИЗМЕНЕНО: Добавлено 'display_total_supply_cost' к base_readonly_fields_tuple
    base_readonly_fields_tuple = ('created_at', 'updated_at', 'created_by', 'payment_transaction_created', 'received_at', 'display_total_supply_cost')

    def display_total_supply_cost(self, obj):
        """Отображает итоговую стоимость поставки."""
        if obj and obj.pk: # Убедимся, что объект существует (уже сохранен)
            return obj.get_total_cost().quantize(Decimal('0.01'))
        return Decimal('0.00') # Для новых, еще не сохраненных поставок
    display_total_supply_cost.short_description = "Итоговая сумма поставки"


    def get_readonly_fields(self, request, obj=None):
        readonly_fields_list = list(self.base_readonly_fields_tuple)

        if obj:
            if obj.status == Supply.STATUS_CANCELLED:
                all_model_fields = [f.name for f in self.model._meta.fields if f.name != self.model._meta.pk.name]
                readonly_fields_list.extend(all_model_fields)
                readonly_fields_list.append('status') # Статус отмененной всегда readonly

            elif obj.status == Supply.STATUS_RECEIVED:
                # Проверяем, можно ли еще отменить поставку
                can_still_be_cancelled = False
                if obj.received_at:
                    if timezone.now() <= obj.received_at + timedelta(hours=24):
                        # Проверка, были ли использованы товары
                        items_not_used = all(item.quantity_remaining_in_batch == item.quantity_received for item in obj.items.all())
                        if items_not_used:
                            can_still_be_cancelled = True
                
                if not can_still_be_cancelled:
                    # Если отменить уже нельзя (прошло >24ч ИЛИ товары использованы), статус становится readonly
                    readonly_fields_list.append('status')
                
                # Ограничения для не-суперпользователей без спец. прав на редактирование оприходованных
                if not request.user.is_superuser and not request.user.has_perm('suppliers.can_edit_received_supply'):
                    fields_to_make_readonly = ['supplier', 'receipt_date', 'document_number', 'notes', 'expected_delivery_date']
                    # Если статус еще не readonly по основной логике, делаем его readonly для этой группы
                    if 'status' not in readonly_fields_list:
                         fields_to_make_readonly.append('status')
                    readonly_fields_list.extend(fields_to_make_readonly)
        
        return tuple(set(readonly_fields_list))

    def get_form(self, request, obj=None, **kwargs):
        """
        Переопределяем форму для динамического изменения choices у поля status.
        """
        form = super().get_form(request, obj, **kwargs)
        if obj and obj.status == Supply.STATUS_RECEIVED:
            # Проверяем, можно ли еще отменить поставку (аналогично get_readonly_fields)
            can_still_be_cancelled = False
            if obj.received_at:
                if timezone.now() <= obj.received_at + timedelta(hours=24):
                    items_not_used = all(item.quantity_remaining_in_batch == item.quantity_received for item in obj.items.all())
                    if items_not_used:
                        can_still_be_cancelled = True
            
            if can_still_be_cancelled:
                # Если можно отменить, оставляем только текущий статус и "Отменено"
                allowed_statuses = [
                    (Supply.STATUS_RECEIVED, dict(Supply.STATUS_CHOICES).get(Supply.STATUS_RECEIVED)),
                    (Supply.STATUS_CANCELLED, dict(Supply.STATUS_CHOICES).get(Supply.STATUS_CANCELLED)),
                ]
                form.base_fields['status'].choices = allowed_statuses
                form.base_fields['status'].widget.choices = allowed_statuses # Для виджета тоже
            # Если отменить нельзя, то get_readonly_fields уже должен был сделать поле status readonly.
            # В этом случае изменение choices не так критично, но для консистентности можно было бы
            # оставить только текущий статус, но это усложнит, если поле уже readonly.
            
        return form

    # ... (get_formsets_with_inlines остается таким же)
    def get_formsets_with_inlines(self, request, obj=None):
        for inline in self.get_inline_instances(request, obj):
            if isinstance(inline, SupplyItemInline):
                current_inline_readonly = list(inline.base_readonly_fields) 
                if obj and obj.status in [Supply.STATUS_RECEIVED, Supply.STATUS_CANCELLED]:
                    current_inline_readonly.extend(['product', 'quantity_received', 'cost_price_per_unit'])
                inline.readonly_fields_set_by_parent = tuple(set(current_inline_readonly))
            yield inline.get_formset(request, obj), inline

    # ... (save_model остается таким же)
    def save_model(self, request, obj: Supply, form, change):
        previous_status_in_db = None
        if obj.pk: 
            try:
                previous_status_in_db = Supply.objects.get(pk=obj.pk).status
            except Supply.DoesNotExist: 
                previous_status_in_db = None 
        else: 
            previous_status_in_db = Supply.STATUS_DRAFT 

        obj._previous_status_in_db = previous_status_in_db
        
        if not obj.pk: 
            obj.created_by = request.user
        
        new_status_from_form = form.cleaned_data.get('status')

        if new_status_from_form == Supply.STATUS_CANCELLED and \
           previous_status_in_db == Supply.STATUS_RECEIVED:
            try:
                print(f"[SupplyAdmin save_model] Поставка #{obj.pk or 'Новая'}: Попытка отмены оприходованной поставки. Запуск проверок.")
                obj._handle_cancellation_checks() 
                print(f"[SupplyAdmin save_model] Поставка #{obj.pk}: Проверки на отмену пройдены.")
            except CannotCancelError as e:
                messages.error(request, str(e))
                print(f"[SupplyAdmin save_model] Поставка #{obj.pk}: Ошибка при проверке отмены - {str(e)}. Сохранение статуса '{new_status_from_form}' отменено.")
                return 
        
        obj.status = new_status_from_form
        super().save_model(request, obj, form, change) 
        
        if obj.status == Supply.STATUS_RECEIVED and \
           previous_status_in_db != Supply.STATUS_RECEIVED and \
           not obj.payment_transaction_created:
            
            print(f"[SupplyAdmin save_model] Поставка #{obj.id}: Условия для создания задачи на оплату выполнены.")
            content_type_supply = ContentType.objects.get_for_model(obj)
            try:
                task_type_supply_payment = TaskType.objects.get(name="Оформить оплату поставки")
                existing_task = Task.objects.filter(
                    content_type=content_type_supply, 
                    object_id=obj.pk, 
                    task_type=task_type_supply_payment
                ).exclude(status__is_final=True).first()

                if not existing_task:
                    initial_status = TaskStatus.objects.get(name="Новая") 
                    assigned_group = task_type_supply_payment.default_visibility_groups.first() 
                    
                    Task.objects.create(
                        title=f"Оформить оплату по поставке №{obj.id}",
                        description=(f"Поставщик: {obj.supplier.name}.\n"
                                     f"Документ: {obj.document_number or 'б/н'}.\n"
                                     f"Дата прихода (документ): {obj.receipt_date.strftime('%d.%m.%Y')}.\n"
                                     f"Дата оприходования: {obj.received_at.strftime('%d.%m.%Y %H:%M') if obj.received_at else 'не оприходовано'}.\n"
                                     f"Сумма к оплате: {obj.get_total_cost()}"), 
                        task_type=task_type_supply_payment, 
                        status=initial_status, 
                        related_object=obj, 
                        created_by=request.user, 
                        assigned_to_group=assigned_group,
                    )
                    messages.success(request, f"Задача на оформление оплаты для поставки #{obj.id} создана.")
                    print(f"[SupplyAdmin save_model] Поставка #{obj.id}: Задача на оформление оплаты СОЗДАНА.")
                else:
                    print(f"[SupplyAdmin save_model] Поставка #{obj.id}: Активная задача (ID: {existing_task.id}) для этой поставки уже существует.")
            except TaskType.DoesNotExist:
                messages.warning(request, "Тип задачи 'Оформить оплату поставки' не найден. Задача не создана.")
            except TaskStatus.DoesNotExist:
                 messages.warning(request, "Начальный статус задачи 'Новая' не найден. Задача не создана.")
            except Exception as e:
                messages.error(request, f"Ошибка при создании задачи на оплату: {e}")
                print(f"[SupplyAdmin save_model] Поставка #{obj.id}: Ошибка при создании задачи - {e}")

    # ... (save_related остается таким же)
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change) 
        supply_instance = form.instance 
        previous_status_in_db = supply_instance._previous_status_in_db
        current_status = supply_instance.status 

        print(f"[SupplyAdmin save_related] Поставка #{supply_instance.id}. Текущий статус: {current_status}, Предыдущий статус из БД: {previous_status_in_db}.")
        
        if current_status == Supply.STATUS_RECEIVED and previous_status_in_db != Supply.STATUS_RECEIVED:
            print(f"[SupplyAdmin save_related] Поставка #{supply_instance.id}: Статус изменился на '{Supply.STATUS_RECEIVED}'. Вызов update_stock_on_received().")
            try:
                supply_instance.update_stock_on_received()
                messages.success(request, f"Поставка #{supply_instance.id} успешно оприходована. Остатки обновлены.")
            except Exception as e:
                messages.error(request, f"Ошибка при оприходовании поставки #{supply_instance.id}: {e}")
                print(f"[SupplyAdmin save_related] Поставка #{supply_instance.id}: Ошибка в update_stock_on_received - {e}")
        elif current_status == Supply.STATUS_CANCELLED and previous_status_in_db == Supply.STATUS_RECEIVED:
            print(f"[SupplyAdmin save_related] Поставка #{supply_instance.id}: Статус изменился на '{Supply.STATUS_CANCELLED}' (была оприходована). Вызов _perform_cancellation_actions().")
            try:
                supply_instance._perform_cancellation_actions()
                messages.success(request, f"Поставка #{supply_instance.id} успешно отменена. Остатки скорректированы.")
            except Exception as e: 
                messages.error(request, f"Критическая ошибка при выполнении отмены поставки #{supply_instance.id}: {e}. "
                                         f"Статус изменен на 'Отменено', но действия по отмене могли быть не завершены. "
                                         f"Проверьте данные!")
                print(f"[SupplyAdmin save_related] Поставка #{supply_instance.id}: Ошибка в _perform_cancellation_actions - {e}")
        
        supply_instance._previous_status_in_db = current_status

    # ... (changeform_view остается таким же)
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            obj = self.get_object(request, object_id)
            if obj:
                if obj.status == Supply.STATUS_CANCELLED:
                    extra_context['title'] = f"Просмотр отмененной поставки: {obj}"
                    messages.warning(request, "Эта поставка отменена. Редактирование невозможно.")
                
                elif obj.status == Supply.STATUS_RECEIVED:
                    extra_context['title'] = f"Просмотр/Редактирование оприходованной поставки: {obj}"
                    if obj.received_at:
                        cancellation_deadline = obj.received_at + timedelta(hours=24)
                        time_now = timezone.now()
                        can_still_cancel_time = time_now <= cancellation_deadline
                        items_not_used = all(item.quantity_remaining_in_batch == item.quantity_received for item in obj.items.all())
                        
                        if can_still_cancel_time and items_not_used:
                            messages.info(request, f"Эту оприходованную поставку можно изменить на статус 'Отменено' "
                                                  f"до {cancellation_deadline.strftime('%d.%m.%Y %H:%M:%S')}.")
                        elif not can_still_cancel_time:
                            messages.warning(request, "Время для отмены этой поставки (24 часа) истекло.")
                        elif not items_not_used: # Если время еще не истекло, но товары использованы
                             messages.warning(request, "Товары из этой поставки были использованы, отмена через смену статуса невозможна.")
                    
                    if not request.user.is_superuser and not request.user.has_perm('suppliers.can_edit_received_supply'):
                        messages.info(request, "Редактирование полей оприходованной поставки ограничено.")
                        
        return super().changeform_view(request, object_id, form_url, extra_context)