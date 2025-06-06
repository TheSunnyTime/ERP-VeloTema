# suppliers/admin.py
from django.contrib import admin, messages
from django.utils.html import format_html
from .models import Supplier, Supply, SupplyItem
from uiconfig.models import SupplyStatusColor

# ИМПОРТЫ ДЛЯ СОЗДАНИЯ ЗАДАЧИ (остаются, если они используются)
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
    # Убрали quantity_remaining_in_batch из fields, т.к. оно будет в readonly_fields
    fields = ('product', 'quantity_received', 'cost_price_per_unit') 
    # quantity_remaining_in_batch теперь всегда readonly в инлайне
    readonly_fields = ('quantity_remaining_in_batch',) 

    def get_readonly_fields(self, request, obj=None):
        # Получаем основной объект Supply через obj.instance (если инлайн на форме редактирования)
        # или через obj, если это сам SupplyItem (но в контексте инлайна нам нужен Supply)
        parent_supply = None
        if hasattr(self, 'parent_model') and obj: # Для Django 3.2+ при редактировании
             # В инлайнах obj это экземпляр SupplyItem, а нам нужен Supply
             # К сожалению, прямого доступа к parent_object из get_readonly_fields инлайна нет.
             # Это ограничение. Мы можем сделать поля инлайна readonly на основе статуса Supply
             # в SupplyAdmin.get_formsets_with_inlines или в SupplyAdmin.get_readonly_fields.
             # Либо, если obj - это SupplyItem, то obj.supply даст нам родительскую поставку.
             # Но get_readonly_fields для инлайна вызывается без родительского obj.
             # Поэтому, если нам нужно сделать инлайн readonly на основе статуса Supply,
             # это лучше делать в SupplyAdmin.
             pass # Оставляем как есть, quantity_remaining_in_batch уже в self.readonly_fields

        # Если сама поставка (obj из SupplyAdmin) имеет статус "Оприходовано" или "Отменено"
        # и у пользователя нет прав на редактирование оприходованных поставок,
        # делаем поля инлайна readonly.
        # Это немного сложнее сделать здесь, так как у инлайна нет прямого доступа к объекту Supply
        # на этапе вызова get_readonly_fields.
        # Основной контроль редактируемости инлайнов при определенных статусах Supply
        # лучше реализовать в SupplyAdmin.get_readonly_fields или has_change_permission.

        # Пока оставляем только quantity_remaining_in_batch как readonly.
        # Редактируемость остальных полей инлайна будет зависеть от общего состояния формы Supply.
        current_readonly_fields = list(self.readonly_fields) # Используем базовые readonly_fields

        # Если есть родительский объект (Supply) и он в статусе "Отменено" или "Оприходовано" (без прав)
        # то делаем все поля инлайна readonly.
        # Это потребует передачи объекта Supply в инлайн, что не стандартно.
        # Проще всего это контролировать через SupplyAdmin.get_readonly_fields,
        # который может сделать все поля формы (включая инлайны) неактивными.

        return tuple(set(current_readonly_fields))


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
        status_display = obj.get_status_display()
        hex_color = self.supply_status_colors_map.get(obj.status)
        if hex_color:
            text_color = '#ffffff' if int(hex_color[1:3], 16) * 0.299 + int(hex_color[3:5], 16) * 0.587 + int(hex_color[5:7], 16) * 0.114 < 128 else '#000000'
            return format_html(
                '<span style="background-color: {0}; padding: 3px 7px; border-radius: 4px; color: {1};"><strong>{2}</strong></span>',
                hex_color,
                text_color,
                status_display
            )
        return status_display
    colored_status.short_description = 'Статус поставки'
    colored_status.admin_order_field = 'status'

    list_display = (
        'id', 
        'supplier', 
        'receipt_date', 
        'document_number', 
        'colored_status', 
        'created_by', 
        'payment_transaction_created',
        'created_at'
    )
    list_filter = (
        'status', 
        'supplier', 
        'receipt_date', 
        'created_by',
        'payment_transaction_created'
    )
    search_fields = ('id', 'supplier__name', 'document_number', 'notes')
    autocomplete_fields = ['supplier', 'created_by']
    inlines = [SupplyItemInline]
    ordering = ('-receipt_date', '-id')
    
    fieldsets = (
        (None, {'fields': ('supplier', 'receipt_date', 'document_number', 'status')}),
        ('Статус оплаты (информация)', {
            'fields': ('payment_transaction_created',) 
        }),
        ('Дополнительно', {'fields': ('notes',)}),
        ('Информация о записи', {
            'fields': ('created_by', ('created_at', 'updated_at')),
            'classes': ('collapse',)
        }),
    )
    
    # Базовые readonly поля
    base_readonly_fields = ('created_at', 'updated_at', 'created_by', 'payment_transaction_created')

    def get_readonly_fields(self, request, obj=None):
        readonly_fields_list = list(self.base_readonly_fields)
        
        if obj: # Если объект существует (форма редактирования)
            # Если статус "Отменено", делаем все поля readonly
            if obj.status == Supply.STATUS_CANCELLED:
                # Добавляем все поля модели, кроме тех, что уже есть, и pk
                all_model_fields = [f.name for f in self.model._meta.fields if f.name != self.model._meta.pk.name]
                readonly_fields_list.extend(all_model_fields)
                # Также делаем инлайны нередактируемыми (это косвенно, т.к. сама форма Supply будет readonly)
                # Чтобы явно заблокировать инлайны, нужно переопределить has_add_permission/has_change_permission/has_delete_permission в инлайне
                # или в get_formsets_with_inlines в SupplyAdmin.
                # Но если основная форма readonly, инлайны обычно тоже не дают сохранить.

            # Если статус "Оприходовано" и нет прав на редактирование оприходованных
            elif obj.status == Supply.STATUS_RECEIVED:
                if not request.user.is_superuser and not request.user.has_perm('suppliers.can_edit_received_supply'):
                    # Делаем все поля, кроме статуса (чтобы его можно было изменить, если есть права на это)
                    # и базовых readonly полей, нередактируемыми.
                    # Поля инлайнов тоже должны стать readonly.
                    fields_to_make_readonly = ['supplier', 'receipt_date', 'document_number', 'notes']
                    # Статус можно оставить редактируемым, если нужно разрешить отмену оприходованной поставки.
                    # Если и статус нельзя менять, то добавить 'status' сюда.
                    readonly_fields_list.extend(fields_to_make_readonly)
            
            # Если статус "Частично оприходовано" - аналогично "Оприходовано" (если правила те же)
            elif obj.status == Supply.STATUS_PARTIALLY_RECEIVED:
                 if not request.user.is_superuser and not request.user.has_perm('suppliers.can_edit_received_supply'): # Предполагаем те же права
                    fields_to_make_readonly = ['supplier', 'receipt_date', 'document_number', 'notes']
                    readonly_fields_list.extend(fields_to_make_readonly)

        return tuple(set(readonly_fields_list))

    def has_change_permission(self, request, obj=None):
        """
        Запрещает изменение объекта, если он в статусе "Отменено".
        """
        if obj and obj.status == Supply.STATUS_CANCELLED:
            return False # Запрещаем доступ к форме изменения
        return super().has_change_permission(request, obj)

    def save_model(self, request, obj: Supply, form, change):
        # Проверка перед сохранением, если вдруг readonly_fields были обойдены
        if obj.pk: # Если объект уже существует
            try:
                original_obj = Supply.objects.get(pk=obj.pk)
                if original_obj.status == Supply.STATUS_CANCELLED and obj.status == Supply.STATUS_CANCELLED:
                    # Если пытаются сохранить уже отмененную поставку без изменения статуса
                    # (например, через какой-то кастомный экшен или если has_change_permission не сработал)
                    if any(form.changed_data): # Проверяем, были ли изменения в форме
                        messages.error(request, "Редактирование отмененной поставки запрещено.")
                        return # Не сохраняем
            except Supply.DoesNotExist:
                pass # Новая, не должна быть отмененной сразу

        # Логика отслеживания previous_status для создания задачи
        previous_status = None
        if obj.pk and change: # Если объект уже существует и это изменение
            try:
                # Получаем статус из БД, так как obj._previous_status может быть неактуален,
                # если объект был загружен, но не сохранен после изменения статуса в форме.
                # obj._previous_status из __init__ хранит статус на момент загрузки объекта.
                previous_status = Supply.objects.get(pk=obj.pk).status
            except Supply.DoesNotExist:
                pass 
        
        # Сохраняем created_by только при создании
        if not obj.pk: 
            obj.created_by = request.user
        
        # Вызываем super().save_model() который вызовет obj.save()
        super().save_model(request, obj, form, change) 

        # obj теперь содержит актуальные данные после сохранения, включая обновленный obj.status
        # и obj._previous_status был обновлен внутри obj.save()

        # Логика создания ЗАДАЧИ (остается как была, но теперь использует актуальный previous_status)
        # Условия для создания задачи:
        # 1. Текущий статус - "Оприходовано"
        # 2. Статус ИЗМЕНИЛСЯ на "Оприходовано" (т.е. previous_status не был "Оприходовано")
        #    ИЛИ это новая запись, которая сразу "Оприходована" (previous_status будет None или начальный статус)
        # 3. И расходная операция по оплате еще НЕ создана (payment_transaction_created is False)
        
        needs_task_creation = False
        if obj.status == Supply.STATUS_RECEIVED and not obj.payment_transaction_created:
            if not change and not previous_status: # Новая запись, сразу "Оприходована"
                needs_task_creation = True
            elif change and previous_status and previous_status != Supply.STATUS_RECEIVED: # Статус изменился на "Оприходовано"
                needs_task_creation = True
        
        if needs_task_creation:
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
                    assigned_group = None
                    if task_type_supply_payment.default_visibility_groups.exists():
                        assigned_group = task_type_supply_payment.default_visibility_groups.first()

                    Task.objects.create(
                        title=f"Оформить оплату по поставке №{obj.id}",
                        description=f"Поставщик: {obj.supplier.name}.\nДокумент: {obj.document_number or 'б/н'}.\nДата поставки: {obj.receipt_date.strftime('%d.%m.%Y')}.\nСумма к оплате: {obj.get_total_cost()}",
                        task_type=task_type_supply_payment,
                        status=initial_status,
                        related_object=obj,
                        created_by=request.user,
                        assigned_to_group=assigned_group,
                    )
                    print(f"INFO (SupplyAdmin): Задача на оформление оплаты для поставки #{obj.id} СОЗДАНА.")
                else:
                    print(f"INFO (SupplyAdmin): Активная задача (ID: {existing_task.id}) на оформление оплаты для поставки #{obj.id} уже существует. Новая не создана.")
            
            except TaskType.DoesNotExist:
                messages.warning(request, "Тип задачи 'Оформить оплату поставки' не найден. Задача не была создана.")
                print(f"ERROR (SupplyAdmin): Тип задачи 'Оформить оплату поставки' не найден. Задача не создана для поставки #{obj.id}.")
            except TaskStatus.DoesNotExist:
                messages.warning(request, "Начальный статус задачи 'Новая' не найден. Задача не была создана.")
                print(f"ERROR (SupplyAdmin): Начальный статус задачи 'Новая' не найден. Задача не создана для поставки #{obj.id}.")
            except Exception as e:
                messages.error(request, f"Произошла ошибка при создании задачи на оплату: {e}")
                print(f"ERROR (SupplyAdmin) при создании задачи для поставки #{obj.id}: {e}")

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """
        Если объект в статусе "Отменено", добавляем сообщение.
        """
        if object_id:
            obj = self.get_object(request, object_id)
            if obj and obj.status == Supply.STATUS_CANCELLED:
                messages.warning(request, "Эта поставка отменена. Редактирование невозможно.")
        return super().changeform_view(request, object_id, form_url, extra_context)

    # Если нужно также запретить удаление отмененных поставок (хотя это может быть не нужно)
    # def has_delete_permission(self, request, obj=None):
    #     if obj and obj.status == Supply.STATUS_CANCELLED:
    #         return False
    #     return super().has_delete_permission(request, obj)