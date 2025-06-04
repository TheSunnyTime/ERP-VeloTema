# suppliers/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Supplier, Supply, SupplyItem
from uiconfig.models import SupplyStatusColor # Ты это уже импортировал

# ИМПОРТЫ ДЛЯ СОЗДАНИЯ ЗАДАЧИ
from tasks.models import Task, TaskType, TaskStatus 
from django.contrib.contenttypes.models import ContentType 

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    # Твой код для SupplierAdmin остается без изменений
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
    # Твой код для SupplyItemInline остается без изменений
    model = SupplyItem
    extra = 1
    autocomplete_fields = ['product']
    fields = ('product', 'quantity_received', 'cost_price_per_unit') # Убрал quantity_remaining_in_batch для чистоты, если оно readonly

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status == Supply.STATUS_RECEIVED:
            if not request.user.is_superuser and not request.user.has_perm('suppliers.can_edit_received_supply'):
                return ['product', 'quantity_received', 'cost_price_per_unit']
        return ['quantity_remaining_in_batch'] # Сделаем его всегда readonly в инлайне, т.к. оно вычисляется
                                             # или управляется логикой FIFO при списании.

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
        # Твой метод colored_status остается без изменений
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
        'payment_transaction_created', # <--- ДОБАВЛЕНО ПОЛЕ
        'created_at'
    )
    list_filter = (
        'status', 
        'supplier', 
        'receipt_date', 
        'created_by',
        'payment_transaction_created'  # <--- ДОБАВЛЕНО ПОЛЕ
    )
    search_fields = ('id', 'supplier__name', 'document_number', 'notes')
    autocomplete_fields = ['supplier', 'created_by']
    inlines = [SupplyItemInline]
    ordering = ('-receipt_date', '-id')
    
    fieldsets = (
        (None, {'fields': ('supplier', 'receipt_date', 'document_number', 'status')}),
        ('Статус оплаты (информация)', { # <--- НОВАЯ СЕКЦИЯ
            'fields': ('payment_transaction_created',) 
        }),
        ('Дополнительно', {'fields': ('notes',)}),
        ('Информация о записи', {
            'fields': ('created_by', ('created_at', 'updated_at')),
            'classes': ('collapse',)
        }),
    )
    # payment_transaction_created управляется системой, так что его можно сделать readonly здесь,
    # но оно будет обновляться через Task.save() -> Supply.save(update_fields=['payment_transaction_created'])
    # Чтобы пользователь случайно не изменил его, добавим в readonly_fields.
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'payment_transaction_created') 

    def save_model(self, request, obj: Supply, form, change):
        # Отслеживаем предыдущий статус для логики создания задачи
        previous_status = None
        if obj.pk: # Если объект уже существует (редактирование)
            try:
                previous_status = Supply.objects.get(pk=obj.pk).status
            except Supply.DoesNotExist:
                pass # Маловероятно, но на всякий случай

        if not obj.pk: # Если это новый объект (создание)
            obj.created_by = request.user
        
        super().save_model(request, obj, form, change) # Сначала сохраняем объект Supply

        # Логика создания ЗАДАЧИ при оприходовании (когда статус меняется на "Оприходовано"
        # или когда новая поставка создается сразу со статусом "Оприходовано")
        
        # obj.status теперь содержит новый сохраненный статус
        # previous_status содержит статус до этого сохранения (или None, если это новая запись)
        
        # Условия для создания задачи:
        # 1. Текущий статус - "Оприходовано"
        # 2. Либо это новая запись, которая сразу "Оприходована"
        #    ЛИБО это существующая запись, и ее статус ИЗМЕНИЛСЯ на "Оприходовано"
        # 3. И расходная операция по оплате еще НЕ создана (payment_transaction_created is False)
        
        needs_task_creation = False
        if obj.status == Supply.STATUS_RECEIVED and not obj.payment_transaction_created:
            if not obj.pk: # Это было новое сохранение, и статус сразу "Оприходовано"
                needs_task_creation = True
            elif previous_status and previous_status != Supply.STATUS_RECEIVED: # Статус изменился на "Оприходовано"
                needs_task_creation = True
        
        if needs_task_creation:
            content_type_supply = ContentType.objects.get_for_model(obj)
            try:
                task_type_supply_payment = TaskType.objects.get(name="Оформить оплату поставки")
                
                # Проверяем, не существует ли уже АКТИВНАЯ (не финальная) задача такого типа для этой поставки
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

                    # Рассчитываем due_date (например, +3 дня от текущей даты)
                    # due_date_for_task = timezone.now() + timezone.timedelta(days=3)

                    Task.objects.create(
                        title=f"Оформить оплату по поставке №{obj.id}",
                        description=f"Поставщик: {obj.supplier.name}.\nДокумент: {obj.document_number or 'б/н'}.\nДата поставки: {obj.receipt_date.strftime('%d.%m.%Y')}.\nСумма к оплате: {obj.get_total_cost()}",
                        task_type=task_type_supply_payment,
                        status=initial_status,
                        related_object=obj,
                        created_by=request.user, # Пользователь, который оприходовал
                        assigned_to_group=assigned_group,
                        # due_date=due_date_for_task # Раскомментируй, если нужно установить срок
                    )
                    print(f"INFO (SupplyAdmin): Задача на оформление оплаты для поставки #{obj.id} СОЗДАНА.")
                else:
                    print(f"INFO (SupplyAdmin): Активная задача (ID: {existing_task.id}) на оформление оплаты для поставки #{obj.id} уже существует. Новая не создана.")
            
            except TaskType.DoesNotExist:
                print(f"ERROR (SupplyAdmin): Тип задачи 'Оформить оплату поставки' не найден. Задача не создана для поставки #{obj.id}.")
            except TaskStatus.DoesNotExist:
                print(f"ERROR (SupplyAdmin): Начальный статус задачи 'Новая' не найден. Задача не создана для поставки #{obj.id}.")
            except Exception as e:
                print(f"ERROR (SupplyAdmin) при создании задачи для поставки #{obj.id}: {e}")

    # save_related остается как был, если он не делает ничего специфичного,
    # кроме вызова super(). Твой существующий код его не менял, так что он в порядке.

    def get_readonly_fields(self, request, obj=None):
        # Твой метод get_readonly_fields для статуса остается без изменений,
        # но мы добавили payment_transaction_created в общий readonly_fields, 
        # так как он должен меняться только системой.
        readonly_fields_list = list(super().get_readonly_fields(request, obj))
        if obj and obj.status == Supply.STATUS_RECEIVED:
            if not request.user.is_superuser and not request.user.has_perm('suppliers.can_edit_received_supply'):
                readonly_fields_list.append('status')
        return tuple(set(readonly_fields_list))