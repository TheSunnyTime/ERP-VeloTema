# F:\CRM 2.0\erp\orders\admin\order_admin.py
from django.contrib import admin, messages
from django.contrib.auth.models import User, Group 
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F 
from decimal import Decimal, ROUND_HALF_UP
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone 
from django.utils.html import format_html
from uiconfig.models import OrderStatusColor, OrderDueDateColorRule 
from ..deadlines.services import calculate_initial_due_date 

from ..models import Order, OrderType
from ..forms import OrderAdminForm
from ..fifo_logic import calculate_and_assign_fifo_cost

from .order_inlines_admin import OrderProductItemInline, OrderServiceItemInline

from salary_management.models import EmployeeRate, SalaryCalculation, SalaryCalculationDetail, ProductSalaryDetail
from utils.models import DocumentTemplate
from products.models import Product
from cash_register.models import CashRegister, CashTransaction


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    form = OrderAdminForm
    list_display = (
        'id',
        'colored_due_date', 
        'display_client_with_phone',
        'display_manager_name',
        'display_performer_name',
        'order_type',
        'repaired_item',
        'colored_status',
        'created_at',
        'get_total_order_amount_display'
    )
    list_filter = (
        'status', 'order_type', 'due_date', 'created_at', 'manager', 'performer', 
        'client',
    )
    search_fields = (
        'id',
        'client__name',
        'client__phone',
        'manager__username', 'manager__first_name',
        'performer__username', 'performer__first_name', 'notes', 'order_type__name'
    )
    autocomplete_fields = ['manager', 'performer', 'client',]
    inlines = [OrderProductItemInline, OrderServiceItemInline]
    change_form_template = 'admin/orders/order/change_form_with_documents.html'

    _status_colors_map_cache = None
    _due_date_color_rules_cache = None

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        # Данные из БД НЕ загружаются здесь при инициализации

    @property
    def status_colors_map(self):
        if self._status_colors_map_cache is None:
            try:
                self._status_colors_map_cache = {
                    color_setting.status_key: color_setting.hex_color
                    for color_setting in OrderStatusColor.objects.all()
                }
            except Exception as e:
                # Логирование ошибки можно добавить, если используется система логирования Django
                # import logging
                # logger = logging.getLogger(__name__)
                # logger.error(f"Error loading OrderStatusColor: {e}", exc_info=True)
                print(f"Error loading OrderStatusColor: {e}") # Для простой отладки
                self._status_colors_map_cache = {} # Возвращаем пустой словарь в случае ошибки
        return self._status_colors_map_cache

    @property
    def due_date_color_rules(self):
        if self._due_date_color_rules_cache is None:
            try:
                self._due_date_color_rules_cache = list(
                    OrderDueDateColorRule.objects.filter(is_active=True).order_by('priority', 'id')
                )
            except Exception as e:
                # import logging
                # logger = logging.getLogger(__name__)
                # logger.error(f"Error loading OrderDueDateColorRule: {e}", exc_info=True)
                print(f"Error loading OrderDueDateColorRule: {e}") # Для простой отладки
                self._due_date_color_rules_cache = [] # Возвращаем пустой список в случае ошибки
        return self._due_date_color_rules_cache
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        order = self.get_object(request, object_id) # Получаем текущий объект заказа
        if order:
            try:
                order_content_type = ContentType.objects.get_for_model(order)
                available_templates = DocumentTemplate.objects.filter(
                    document_type__related_model=order_content_type, 
                    is_active=True
                )
                extra_context['available_document_templates'] = available_templates
                extra_context['current_object_id'] = object_id 
                # Добавим статус заказа, если он нужен в шаблоне для кнопок
                extra_context['current_order_status_is_issued'] = (order.status == Order.STATUS_ISSUED)
                print(f"[OrderAdmin change_view] Для заказа ID {object_id} найдено шаблонов: {available_templates.count()}") # Отладка
            except ContentType.DoesNotExist:
                extra_context['available_document_templates'] = None
                messages.warning(request, "Не удалось определить тип контента для Заказа при поиске шаблонов документов.")
                print(f"[OrderAdmin change_view] ContentType не найден для заказа ID {object_id}") # Отладка
            except Exception as e:
                extra_context['available_document_templates'] = None
                messages.error(request, f"Ошибка при получении шаблонов документов: {str(e)}")
                print(f"[OrderAdmin change_view] Ошибка получения шаблонов для заказа ID {object_id}: {e}") # Отладка
        else:
            print(f"[OrderAdmin change_view] Заказ с ID {object_id} не найден.") # Отладка
        
        # Не забываем добавить print для всего extra_context перед вызовом super
        print(f"[OrderAdmin change_view] extra_context передаваемый в шаблон: {extra_context}")
        return super().change_view(request, object_id, form_url, extra_context=extra_context)


    def display_client_with_phone(self, obj):
        if obj.client:
            client_name = str(obj.client)
            phone_to_display = obj.client.phone
            if phone_to_display:
                client_url = reverse('admin:clients_client_change', args=[obj.client.pk])
                return format_html('<a href="{}">{} ({})</a>', client_url, client_name, phone_to_display)
            else:
                client_url = reverse('admin:clients_client_change', args=[obj.client.pk])
                return format_html('<a href="{}">{}</a>', client_url, client_name)
        return "N/A"
    display_client_with_phone.short_description = "Клиент (телефон)"
    display_client_with_phone.admin_order_field = 'client'

    def display_manager_name(self, obj):
        if obj.manager:
            return obj.manager.first_name if obj.manager.first_name else obj.manager.username
        return "N/A"
    display_manager_name.short_description = "Менеджер"
    display_manager_name.admin_order_field = 'manager__first_name'

    def display_performer_name(self, obj):
        if obj.performer:
            return obj.performer.first_name if obj.performer.first_name else obj.performer.username
        return "N/A"
    display_performer_name.short_description = "Исполнитель"
    display_performer_name.admin_order_field = 'performer__first_name'

    def get_total_order_amount_display(self, obj):
        if obj.pk: return obj.calculate_total_amount()
        return Decimal('0.00')
    get_total_order_amount_display.short_description = "Общая сумма заказа"

    def colored_status(self, obj):
        status_key = obj.status
        display_name = obj.get_status_display()
        # self.status_colors_map теперь является property, которое загрузит данные при первом обращении
        hex_color = self.status_colors_map.get(status_key, '#FFFFFF') 
        try:
            r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            text_color = '#000000' if luminance > 0.5 else '#FFFFFF'
        except:
            text_color = '#000000' 
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 5px 10px; border-radius: 4px;">{}</span>',
            hex_color, text_color, display_name,
        )
    colored_status.short_description = "Статус"
    colored_status.admin_order_field = 'status'

    def get_due_date_style(self, due_date):
        if not due_date:
            return None
        today = timezone.now().date()
        days_remaining = (due_date - today).days
        # self.due_date_color_rules теперь является property
        for rule in self.due_date_color_rules: 
            if rule.check_condition(days_remaining):
                hex_bg_color = rule.hex_color
                try:
                    r, g, b = int(hex_bg_color[1:3], 16), int(hex_bg_color[3:5], 16), int(hex_bg_color[5:7], 16)
                    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                    text_color = '#000000' if luminance > 0.5 else '#FFFFFF'
                except:
                    text_color = '#000000'
                return {'background_color': hex_bg_color, 'text_color': text_color}
        return None

    def colored_due_date(self, obj):
        if not obj.due_date:
            return "–"
        date_str = obj.due_date.strftime("%d.%m.%Y")
        style = self.get_due_date_style(obj.due_date)
        if style:
            return format_html(
                '<span style="background-color: {}; color: {}; padding: 2px 5px; border-radius: 3px; white-space: nowrap;">{}</span>',
                style['background_color'],
                style['text_color'],
                date_str
            )
        return date_str
    colored_due_date.short_description = "Срок до"
    colored_due_date.admin_order_field = 'due_date'

    def get_fieldsets(self, request, obj=None):
        main_fields_tuple = ('client', 'manager', 'performer', 'order_type', 'repaired_item', 'status', 'notes')
        payment_closure_fieldset_fields = ['payment_method_on_closure']
        if request.user.is_superuser or request.user.has_perm('orders.can_view_target_cash_register'):
            payment_closure_fieldset_fields.append('target_cash_register')

        date_info_fields_base = ['created_at', 'updated_at', 'due_date'] 

        if obj: 
            current_main_fields = list(main_fields_tuple)
            fieldsets_config = (
                (None, {'fields': tuple(current_main_fields)}),
                ('Оплата и закрытие заказа', {'fields': tuple(payment_closure_fieldset_fields)}),
                ('Суммы и даты (информация)', {
                    'fields': ('get_total_order_amount_display',) + tuple(date_info_fields_base) 
                }),
            )
            return fieldsets_config
        else: 
            new_order_main_fields = list(main_fields_tuple)
            if 'manager' in new_order_main_fields: new_order_main_fields.remove('manager')
            payment_closure_fieldset_fields_new = ['payment_method_on_closure']
            
            fieldsets_config_new = (
                (None, {'fields': tuple(new_order_main_fields)}),
                ('Оплата и закрытие заказа', {'fields': tuple(payment_closure_fieldset_fields_new)}),
                ('Суммы и даты (информация)', {
                    'fields': ('get_total_order_amount_display',) + tuple(date_info_fields_base) 
                }),
            )
            return fieldsets_config_new

    def get_readonly_fields(self, request, obj=None):
        base_readonly = ['created_at', 'updated_at', 'due_date', 'get_total_order_amount_display'] 
        db_obj = None
        if obj and obj.pk:
            try: db_obj = self.model.objects.get(pk=obj.pk)
            except self.model.DoesNotExist: db_obj = obj
        else: db_obj = obj
        
        obj_to_check_status = db_obj if db_obj else obj
        
        if obj_to_check_status and obj_to_check_status.pk:
            can_edit_order_manager_group_name = "Редакторы ответственных в заказах" 
            user_can_edit_manager = request.user.is_superuser or request.user.groups.filter(name=can_edit_order_manager_group_name).exists()
            if not user_can_edit_manager: base_readonly.append('manager')
            
            if obj_to_check_status.status == Order.STATUS_ISSUED:
                base_readonly.extend(['status', 'payment_method_on_closure', 'client', 'manager', 'performer', 'order_type'])
            else:
                if not request.user.has_perm('orders.can_change_order_type_dynamically'): base_readonly.append('order_type')
        else: 
            base_readonly.extend(['status', 'order_type', 'payment_method_on_closure', 'target_cash_register'])
        
        return tuple(set(base_readonly)) 

    def get_form(self, request, obj=None, **kwargs):
        if obj and obj.pk:
            try:
                db_instance = Order.objects.get(pk=obj.pk)
                setattr(request, '_current_order_previous_status_from_db', db_instance.status)
            except Order.DoesNotExist:
                setattr(request, '_current_order_previous_status_from_db', Order.STATUS_NEW if not obj.pk else obj.status)
        else:
            setattr(request, '_current_order_previous_status_from_db', Order.STATUS_NEW)
        form = super().get_form(request, obj, **kwargs)
        if obj is None: 
            new_status_choices = [choice for choice in Order.STATUS_CHOICES if choice[0] != Order.STATUS_ISSUED]
            if 'status' in form.base_fields:
                form.base_fields['status'].choices = new_status_choices
                form.base_fields['status'].initial = Order.STATUS_NEW
            if 'manager' in form.base_fields: 
                form.base_fields['manager'].widget = admin.widgets.HiddenInput()
                form.base_fields['manager'].required = False 
        return form

    def _get_or_create_salary_calculation(self, request, order_instance, employee, role_context_key, role_verbose_name):
        salary_calc_obj, calc_created = SalaryCalculation.objects.get_or_create(
            employee=employee, order=order_instance, role_context=role_context_key,
            defaults={
                'period_date': order_instance.updated_at.date(),
                'applied_base_rule_info': f"Расчет для {employee} по заказу #{order_instance.id} ({role_verbose_name})",
                'calculation_type': "Сдельная оплата по заказу (авто)",
                'total_calculated_amount': Decimal('0.00')
            }
        )
        was_preexisting_with_amount = False
        if not calc_created and salary_calc_obj.total_calculated_amount > Decimal('0.00'):
            was_preexisting_with_amount = True
        return salary_calc_obj, calc_created, was_preexisting_with_amount

    def save_model(self, request, obj, form, change):
        previous_status_in_db_before_save = None
        if obj.pk:
            try:
                previous_status_in_db_before_save = Order.objects.get(pk=obj.pk).status
            except Order.DoesNotExist:
                previous_status_in_db_before_save = Order.STATUS_NEW if not change else None
        else: 
            previous_status_in_db_before_save = Order.STATUS_NEW 
        
        setattr(request, '_current_order_previous_status_from_db_for_save_related', previous_status_in_db_before_save)
        
        if not change: 
            if not obj.manager_id: 
                obj.manager = request.user
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change) 
        
        order_instance = form.instance 
        
        print(f"[OrderAdmin SaveRelated] НАЧАЛО для заказа ID: {order_instance.id}. Тип до определения: {order_instance.order_type}")

        original_order_type_before_determination = order_instance.order_type
        type_changed_by_determination = False
        
        if order_instance.determine_and_set_order_type():
            if order_instance.order_type != original_order_type_before_determination:
                type_changed_by_determination = True
        
        print(f"[OrderAdmin SaveRelated] Заказ ID: {order_instance.id}. Тип ПОСЛЕ определения: {order_instance.order_type}. Тип изменился: {type_changed_by_determination}")

        recalculate_due_date_in_save_related = False
        if order_instance.order_type and order_instance.order_type.name == OrderType.TYPE_REPAIR:
            if (not change) or \
               (type_changed_by_determination and order_instance.order_type.name == OrderType.TYPE_REPAIR) or \
               (order_instance.due_date is None):
                recalculate_due_date_in_save_related = True
                print(f"[OrderAdmin SaveRelated] Заказ ID {order_instance.id} (тип {order_instance.order_type}). Требуется установка/пересчет due_date.")

        if recalculate_due_date_in_save_related:
            new_due_date = calculate_initial_due_date(order_instance)
            if order_instance.due_date != new_due_date:
                print(f"[OrderAdmin SaveRelated] Заказ ID {order_instance.id}. Старый due_date: {order_instance.due_date}, Новый due_date: {new_due_date}")
                order_instance.due_date = new_due_date
            else:
                print(f"[OrderAdmin SaveRelated] Заказ ID {order_instance.id}. due_date ({order_instance.due_date}) уже соответствует расчетному ({new_due_date}). Обновление не требуется.")
        
        previous_db_status = getattr(request, '_current_order_previous_status_from_db_for_save_related', None)
        current_status_on_form = order_instance.status
        
        is_newly_issued_attempt = (
            order_instance.pk is not None and
            current_status_on_form == Order.STATUS_ISSUED and
            (previous_db_status is None or previous_db_status != Order.STATUS_ISSUED) 
        )
        
        operations_successful = False 
        fields_to_update_initial = [] # Поля, которые нужно сохранить до или в начале блока выдачи

        if type_changed_by_determination and order_instance.order_type != original_order_type_before_determination:
            fields_to_update_initial.append('order_type')
        
        if recalculate_due_date_in_save_related and (original_order_type_before_determination is None or order_instance.due_date != getattr(original_order_type_before_determination, 'due_date', None)): # Проверяем, изменился ли due_date
            fields_to_update_initial.append('due_date')

        # Сохраняем тип/срок, если они изменились, ДО основной логики выдачи
        if fields_to_update_initial:
            fields_to_update_initial.append('updated_at')
            order_instance.updated_at = timezone.now()
            order_instance.save(update_fields=list(set(fields_to_update_initial)))
            print(f"[OrderAdmin SaveRelated] Заказ ID {order_instance.id}. Предварительно сохранены поля: {fields_to_update_initial}")
            if 'order_type' in fields_to_update_initial:
                 messages.info(request, f"Тип заказа №{order_instance.id} автоматически определен/обновлен на '{order_instance.order_type}'.")
            if 'due_date' in fields_to_update_initial:
                 messages.info(request, f"Срок выполнения для заказа №{order_instance.id} обновлен на {order_instance.due_date.strftime('%d.%m.%Y')}.")


        if is_newly_issued_attempt:
            print(f"[OrderAdmin SaveRelated] Попытка выдачи заказа ID {order_instance.id}. Предыдущий статус в БД: {previous_db_status}, Текущий на форме: {current_status_on_form}")
            original_target_cash_register_id = order_instance.target_cash_register_id

            try:
                print(f"[OrderAdmin SaveRelated] Проверка условий для выдачи заказа ID {order_instance.id}")
                if not order_instance.payment_method_on_closure: raise ValidationError("Метод оплаты должен быть указан.")
                if order_instance.order_type and order_instance.order_type.name == OrderType.TYPE_REPAIR and not order_instance.performer: raise ValidationError(f"Исполнитель должен быть указан для '{OrderType.TYPE_REPAIR}'.")
                
                determined_cash_register_qs = CashRegister.objects.none()
                if order_instance.payment_method_on_closure == Order.ORDER_PAYMENT_METHOD_CASH: determined_cash_register_qs = CashRegister.objects.filter(is_default_for_cash=True, is_active=True)
                elif order_instance.payment_method_on_closure == Order.ORDER_PAYMENT_METHOD_CARD: determined_cash_register_qs = CashRegister.objects.filter(is_default_for_card=True, is_active=True)
                if not determined_cash_register_qs.exists(): raise ValidationError("Касса по умолчанию для выбранного метода оплаты не найдена.")
                if determined_cash_register_qs.count() > 1: raise ValidationError("Найдено несколько касс по умолчанию для выбранного метода оплаты.")
                determined_cash_register = determined_cash_register_qs.first()
                print(f"[OrderAdmin SaveRelated] Определена касса для зачисления: {determined_cash_register}")
                
                current_order_total = order_instance.calculate_total_amount()
                if not (current_order_total > Decimal('0.00')): raise ValidationError(f"Сумма заказа ({current_order_total}) должна быть > 0 для выдачи.")
                print(f"[OrderAdmin SaveRelated] Общая сумма заказа для выдачи: {current_order_total}")

                with transaction.atomic():
                    print(f"[OrderAdmin SaveRelated] Начало транзакции для заказа ID {order_instance.id}")
                    
                    # FIFO и списание остатков
                    print(f"[OrderAdmin SaveRelated - FIFO] Расчет FIFO и списание остатков для заказа ID {order_instance.id}")
                    for item_idx, order_item_instance in enumerate(order_instance.product_items.all()):
                        print(f"[OrderAdmin SaveRelated - FIFO] Товар {item_idx+1}: {order_item_instance.product.name}")
                        calculate_and_assign_fifo_cost(order_item_instance)
                        order_item_instance.save(update_fields=['cost_price_at_sale'])
                        print(f"[OrderAdmin SaveRelated - FIFO] Себестоимость (FIFO) для {order_item_instance.product.name}: {order_item_instance.cost_price_at_sale}")
                    
                    for item_idx, item_to_update_stock in enumerate(order_instance.product_items.all()):
                        print(f"[OrderAdmin SaveRelated - Stock] Списание товара {item_idx+1}: {item_to_update_stock.product.name}, кол-во: {item_to_update_stock.quantity}")
                        product_to_update = Product.objects.select_for_update().get(pk=item_to_update_stock.product.pk)
                        if product_to_update.stock_quantity < item_to_update_stock.quantity:
                            raise ValidationError(f"Недостаточно общего остатка товара '{product_to_update.name}' (в наличии: {product_to_update.stock_quantity}, требуется: {item_to_update_stock.quantity})")
                        product_to_update.stock_quantity -= item_to_update_stock.quantity
                        product_to_update.updated_at = timezone.now()
                        product_to_update.save(update_fields=['stock_quantity', 'updated_at'])
                        print(f"[OrderAdmin SaveRelated - Stock] Остаток {product_to_update.name} обновлен: {product_to_update.stock_quantity}")
                    
                    order_instance.target_cash_register = determined_cash_register
                    order_instance.updated_at = timezone.now() 
                    # Статус 'Выдан' уже должен быть установлен в order_instance из формы
                    # и сохранен в save_model. Здесь мы сохраняем target_cash_register и updated_at.
                    order_instance.save(update_fields=['target_cash_register', 'updated_at']) 
                    print(f"[OrderAdmin SaveRelated] Заказ ID {order_instance.id} обновлен: target_cash_register, updated_at.")

                    if not CashTransaction.objects.filter(order=order_instance, transaction_type=CashTransaction.TRANSACTION_TYPE_INCOME).exists():
                        CashTransaction.objects.create(
                            cash_register=order_instance.target_cash_register, 
                            transaction_type=CashTransaction.TRANSACTION_TYPE_INCOME, 
                            payment_method=order_instance.payment_method_on_closure, 
                            amount=current_order_total, 
                            employee=order_instance.manager, 
                            order=order_instance, 
                            description=f"Оплата по заказу №{order_instance.id} (статус Выдан)"
                        )
                        print(f"[OrderAdmin SaveRelated] Создана кассовая транзакция для заказа ID {order_instance.id}")

                    # --- НАЧАЛО БЛОКА РАСЧЕТА ЗАРПЛАТЫ (С ОТЛАДКОЙ) ---
                    print(f"[OrderAdmin SaveRelated - ЗП] >>> НАЧАЛО БЛОКА РАСЧЕТА ЗАРПЛАТЫ для заказа ID: {order_instance.id}")
                    earners_to_process = []
                    if order_instance.manager:
                        print(f"[OrderAdmin SaveRelated - ЗП] Менеджер найден: {order_instance.manager.username}")
                        earners_to_process.append({'employee_obj': order_instance.manager, 'role_key_for_rate': EmployeeRate.ROLE_MANAGER, 'role_verbose': 'Менеджер', 'salary_calc_role_context': SalaryCalculation.ROLE_CONTEXT_MANAGER})
                    else:
                        print(f"[OrderAdmin SaveRelated - ЗП] Менеджер НЕ найден для заказа ID: {order_instance.id}")

                    if order_instance.performer:
                        print(f"[OrderAdmin SaveRelated - ЗП] Исполнитель найден: {order_instance.performer.username}")
                        earners_to_process.append({'employee_obj': order_instance.performer, 'role_key_for_rate': EmployeeRate.ROLE_PERFORMER, 'role_verbose': 'Исполнитель', 'salary_calc_role_context': SalaryCalculation.ROLE_CONTEXT_PERFORMER})
                    else:
                        print(f"[OrderAdmin SaveRelated - ЗП] Исполнитель НЕ найден для заказа ID: {order_instance.id}")

                    print(f"[OrderAdmin SaveRelated - ЗП] Список сотрудников для обработки ЗП: {len(earners_to_process)} человек")
                    any_salary_calculated_this_session = False
                    for earner_info_idx, earner_info in enumerate(earners_to_process):
                        employee = earner_info['employee_obj']
                        role_key_for_rate = earner_info['role_key_for_rate']
                        role_verbose_name = earner_info['role_verbose']
                        salary_calc_context_key = earner_info['salary_calc_role_context']
                        print(f"[OrderAdmin SaveRelated - ЗП] --- Обработка сотрудника {earner_info_idx+1}: {employee.username}, Роль: {role_verbose_name}")
                        print(f"[OrderAdmin SaveRelated - ЗП] Тип текущего заказа: {order_instance.order_type}")
                        employee_rate_instance = None
                        if order_instance.order_type:
                            try:
                                employee_rate_instance = EmployeeRate.objects.get(employee=employee, order_type=order_instance.order_type, role_in_order=role_key_for_rate, is_active=True)
                                print(f"[OrderAdmin SaveRelated - ЗП] Найдена активная ставка EmployeeRate ID {employee_rate_instance.id}: Услуги {employee_rate_instance.service_percentage}%, Прибыль с товаров {employee_rate_instance.product_profit_percentage}%")
                            except EmployeeRate.DoesNotExist: print(f"[OrderAdmin SaveRelated - ЗП] ВНИМАНИЕ: Активная ставка EmployeeRate НЕ НАЙДЕНА для {employee.username} (Роль: {role_verbose_name}, Тип заказа: {order_instance.order_type})")
                            except EmployeeRate.MultipleObjectsReturned: print(f"[OrderAdmin SaveRelated - ЗП] ВНИМАНИЕ: Найдено НЕСКОЛЬКО активных ставок EmployeeRate. Используется первая."); employee_rate_instance = EmployeeRate.objects.filter(employee=employee, order_type=order_instance.order_type, role_in_order=role_key_for_rate, is_active=True).first()
                        else: print(f"[OrderAdmin SaveRelated - ЗП] ВНИМАНИЕ: Тип заказа не определен, не могу найти ставку для {employee.username}")
                        if not employee_rate_instance: messages.warning(request, f"Активная ставка для {employee.first_name or employee.username} ({role_verbose_name}) для типа заказа '{order_instance.order_type}' не найдена. ЗП не начислена."); print(f"[OrderAdmin SaveRelated - ЗП] Пропуск ЗП для {employee.username} из-за отсутствия ставки."); continue
                        salary_calc_obj, sc_created, sc_preexisting_non_zero_calc = self._get_or_create_salary_calculation(request, order_instance, employee, salary_calc_context_key, role_verbose_name)
                        print(f"[OrderAdmin SaveRelated - ЗП] SalaryCalculation для {employee.username}: {'СОЗДАН' if sc_created else 'СУЩЕСТВУЕТ (ID: '+str(salary_calc_obj.id)+')'}. Был с суммой: {sc_preexisting_non_zero_calc}")
                        if not sc_created: print(f"[OrderAdmin SaveRelated - ЗП] Очистка старых деталей ЗП для SalaryCalculation ID: {salary_calc_obj.id}"); salary_calc_obj.service_details.all().delete(); salary_calc_obj.product_profit_details.all().delete(); salary_calc_obj.total_calculated_amount = Decimal('0.00')
                        current_session_earned_total_for_role = Decimal('0.00')
                        can_earn_from_services_for_role = True
                        if order_instance.order_type and order_instance.order_type.name == OrderType.TYPE_SALE and role_key_for_rate == EmployeeRate.ROLE_PERFORMER: can_earn_from_services_for_role = False; print(f"[OrderAdmin SaveRelated - ЗП] Исполнитель не получает ЗП с услуг для типа заказа 'Продажа'")
                        if can_earn_from_services_for_role and employee_rate_instance.service_percentage > Decimal('0.00'):
                            print(f"[OrderAdmin SaveRelated - ЗП] Расчет ЗП от УСЛУГ для {employee.username}, %: {employee_rate_instance.service_percentage}")
                            for service_item_idx, service_item in enumerate(order_instance.service_items.all()):
                                base_amount_for_service_calc = service_item.get_item_total(); print(f"[OrderAdmin SaveRelated - ЗП] Услуга {service_item_idx+1}: '{service_item.service.name}', Сумма: {base_amount_for_service_calc}")
                                if base_amount_for_service_calc is not None and base_amount_for_service_calc > Decimal('0.00'):
                                    earned_from_service = (base_amount_for_service_calc * (employee_rate_instance.service_percentage / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                                    if earned_from_service > Decimal('0.00'): SalaryCalculationDetail.objects.create(salary_calculation=salary_calc_obj, order_service_item=service_item, source_description=service_item.service.name, base_amount_for_calc=base_amount_for_service_calc, applied_percentage=employee_rate_instance.service_percentage, earned_amount=earned_from_service, detail_type=f"service_{role_key_for_rate}"); current_session_earned_total_for_role += earned_from_service; print(f"[OrderAdmin SaveRelated - ЗП] +{earned_from_service} руб. от услуги '{service_item.service.name}'")
                        if employee_rate_instance.product_profit_percentage > Decimal('0.00'):
                            print(f"[OrderAdmin SaveRelated - ЗП] Расчет ЗП от ПРИБЫЛИ С ТОВАРОВ для {employee.username}, %: {employee_rate_instance.product_profit_percentage}")
                            for item_idx_prod, item in enumerate(order_instance.product_items.all()):
                                print(f"[OrderAdmin SaveRelated - ЗП] Товар {item_idx_prod+1}: '{item.product.name}', Цена: {item.price_at_order}, Себест.(FIFO): {item.cost_price_at_sale}, Кол-во: {item.quantity}")
                                if item.price_at_order is not None and item.cost_price_at_sale is not None and item.quantity > 0:
                                    profit_per_unit = item.price_at_order - item.cost_price_at_sale; total_profit_for_line = profit_per_unit * item.quantity; print(f"[OrderAdmin SaveRelated - ЗП] Прибыль с '{item.product.name}': {total_profit_for_line}")
                                    if total_profit_for_line > Decimal('0.00'):
                                        earned_from_profit = (total_profit_for_line * (employee_rate_instance.product_profit_percentage / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                                        if earned_from_profit > Decimal('0.00'): ProductSalaryDetail.objects.create(salary_calculation=salary_calc_obj, order_product_item=item, product_name_snapshot=item.product.name, product_price_at_sale=item.price_at_order, product_cost_at_sale=item.cost_price_at_sale, profit_from_item=total_profit_for_line.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), applied_percentage=employee_rate_instance.product_profit_percentage, earned_amount=earned_from_profit); current_session_earned_total_for_role += earned_from_profit; print(f"[OrderAdmin SaveRelated - ЗП] +{earned_from_profit} руб. от прибыли с товара '{item.product.name}'")
                                else: print(f"[OrderAdmin SaveRelated - ЗП] Пропуск прибыли для '{item.product.name}': нет цены/себест.")
                        print(f"[OrderAdmin SaveRelated - ЗП] Итого начислено для {employee.username} в этой сессии: {current_session_earned_total_for_role}")
                        if current_session_earned_total_for_role > Decimal('0.00') or sc_created or (not sc_created and sc_preexisting_non_zero_calc and salary_calc_obj.total_calculated_amount != current_session_earned_total_for_role):
                            salary_calc_obj.total_calculated_amount = current_session_earned_total_for_role.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP); rule_parts = []; service_details_exist = salary_calc_obj.service_details.filter(earned_amount__gt=0).exists(); product_details_exist = salary_calc_obj.product_profit_details.filter(earned_amount__gt=0).exists()
                            if service_details_exist: rule_parts.append(f"Услуги: {employee_rate_instance.service_percentage}%")
                            if product_details_exist: rule_parts.append(f"Приб.тов.: {employee_rate_instance.product_profit_percentage}%")
                            salary_calc_obj.applied_base_rule_info = f"Ставка для {role_verbose_name} ({employee.username}) в заказе типа '{order_instance.order_type.name if order_instance.order_type else 'N/A'}': {'; '.join(rule_parts) if rule_parts else 'Ставка применена, начислений нет'}."; salary_calc_obj.calculation_type = f"Сдельная ({role_verbose_name})"; salary_calc_obj.period_date = order_instance.updated_at.date(); salary_calc_obj.save(); any_salary_calculated_this_session = True
                            print(f"[OrderAdmin SaveRelated - ЗП] СОХРАНЕНА SalaryCalculation для {employee.username}, ID: {salary_calc_obj.id}, Сумма: {salary_calc_obj.total_calculated_amount}, Инфо: {salary_calc_obj.applied_base_rule_info}")
                            messages.success(request, f"Зарплата для {employee.first_name or employee.username} (Роль: {role_verbose_name}) по заказу #{order_instance.id} начислена/обновлена: {salary_calc_obj.total_calculated_amount} руб.")
                        elif not sc_created and not sc_preexisting_non_zero_calc and current_session_earned_total_for_role == Decimal('0.00'): messages.info(request, f"Для {employee.first_name or employee.username} (Роль: {role_verbose_name}) по заказу #{order_instance.id} в этой сессии начислений не произведено (сумма 0)."); print(f"[OrderAdmin SaveRelated - ЗП] Для {employee.username} начислений не было (сумма 0), SalaryCalculation не обновлялся.")
                    if any_salary_calculated_this_session: print(f"[OrderAdmin SaveRelated - ЗП] Зарплаты были начислены. Обновление updated_at для заказа ID: {order_instance.id}"); order_instance.updated_at = timezone.now(); order_instance.save(update_fields=['updated_at'])
                    else: print(f"[OrderAdmin SaveRelated - ЗП] В этой сессии не было начислено ни одной зарплаты для заказа ID: {order_instance.id}")
                    print(f"[OrderAdmin SaveRelated - ЗП] <<< КОНЕЦ БЛОКА РАСЧЕТА ЗАРПЛАТЫ для заказа ID: {order_instance.id}")
                    # --- КОНЕЦ БЛОКА РАСЧЕТА ЗАРПЛАТЫ ---

                    operations_successful = True
                    print(f"[OrderAdmin SaveRelated] Все операции при выдаче заказа ID {order_instance.id} успешно завершены.")
            except ValidationError as e:
                messages.error(request, f"Не удалось завершить выдачу заказа №{order_instance.id}: {str(e)}")
                print(f"[OrderAdmin SaveRelated] ValidationError при выдаче заказа ID {order_instance.id}: {e}")
            finally:
                if not operations_successful and previous_db_status is not None:
                    if previous_db_status != Order.STATUS_ISSUED: 
                        Order.objects.filter(pk=order_instance.pk).update(
                            status=previous_db_status, 
                            updated_at=timezone.now(), 
                            target_cash_register_id=original_target_cash_register_id 
                        )
                        form.instance.status = previous_db_status 
                        form.instance.target_cash_register_id = original_target_cash_register_id 
                        messages.info(request, f"Статус заказа №{order_instance.id} возвращен на '{order_instance.get_status_display_for_key(previous_db_status)}'. Операции по выдаче отменены.")
                        print(f"[OrderAdmin SaveRelated] Статус заказа ID {order_instance.id} ОТКАЧЕН на '{previous_db_status}'")
        
        # Сохранение типа/срока, если они менялись, и это не была операция выдачи (или она не удалась)
        elif type_changed_by_determination or (recalculate_due_date_in_save_related and order_instance.due_date != getattr(original_order_type_before_determination, 'due_date', None) and not original_order_type_before_determination and not hasattr(original_order_type_before_determination, 'due_date')): # Уточнено условие для due_date
             # Этот блок теперь вызывается только если НЕ is_newly_issued_attempt
             # или если is_newly_issued_attempt, но operations_successful = False (хотя тогда откат статуса)
             # По сути, если тип или срок изменились и заказ НЕ ВЫДАЕТСЯ УСПЕШНО.
            fields_to_save_finally = []
            if type_changed_by_determination and order_instance.order_type != original_order_type_before_determination:
                fields_to_save_finally.append('order_type')
            if recalculate_due_date_in_save_related and order_instance.due_date != getattr(original_order_type_before_determination, 'due_date', None) and not original_order_type_before_determination and not hasattr(original_order_type_before_determination, 'due_date'):
                fields_to_save_finally.append('due_date')
            
            if fields_to_save_finally:
                print(f"[OrderAdmin SaveRelated] Финальное сохранение (вне блока выдачи) для заказа ID {order_instance.id}. Поля: {fields_to_save_finally}")
                fields_to_save_finally.append('updated_at')
                order_instance.updated_at = timezone.now()
                order_instance.save(update_fields=list(set(fields_to_save_finally)))
                if 'order_type' in fields_to_save_finally:
                    messages.info(request, f"Тип заказа №{order_instance.id} автоматически определен/обновлен на '{order_instance.order_type}'.")
                if 'due_date' in fields_to_save_finally:
                    messages.info(request, f"Срок выполнения для заказа №{order_instance.id} обновлен на {order_instance.due_date.strftime('%d.%m.%Y')}.")
        
        print(f"[OrderAdmin SaveRelated] КОНЕЦ для заказа ID: {order_instance.id}")



    class Media:
        js = (
            'admin/js/jquery.init.js', 
            'orders/js/order_form_price_updater.js',
            'orders/js/order_form_conditional_fields.js',
            'orders/js/adaptive_client_field.js', 
        )
        css = {
            'all': ('orders/css/admin_order_form.css',)
        }