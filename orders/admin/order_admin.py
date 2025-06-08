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
# --- ИЗМЕНЕННЫЙ ИМПОРТ ---
from ..deadlines.services import determine_and_update_order_due_date, is_order_complex, REPAIR_ORDER_TYPE_NAME 

from ..models import Order, OrderType # REPAIR_ORDER_TYPE_NAME теперь импортируется из deadlines.services
from ..forms import OrderAdminForm
from ..fifo_logic import calculate_and_assign_fifo_cost

from .order_inlines_admin import OrderProductItemInline, OrderServiceItemInline

from salary_management.models import EmployeeRate, SalaryCalculation, SalaryCalculationDetail, ProductSalaryDetail
from utils.models import DocumentTemplate
from products.models import Product
from cash_register.models import CashRegister, CashTransaction


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # ... (list_display, list_filter, etc. без изменений) ...
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
        'status', 'order_type', 'due_date','manager', 'performer', 
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

    @property
    def status_colors_map(self):
        if self._status_colors_map_cache is None:
            try:
                self._status_colors_map_cache = {
                    color_setting.status_key: color_setting.hex_color
                    for color_setting in OrderStatusColor.objects.all()
                }
            except Exception as e:
                print(f"Error loading OrderStatusColor: {e}") 
                self._status_colors_map_cache = {}
        return self._status_colors_map_cache

    @property
    def due_date_color_rules(self):
        if self._due_date_color_rules_cache is None:
            try:
                self._due_date_color_rules_cache = list(
                    OrderDueDateColorRule.objects.filter(is_active=True).order_by('priority', 'id')
                )
            except Exception as e:
                print(f"Error loading OrderDueDateColorRule: {e}")
                self._due_date_color_rules_cache = []
        return self._due_date_color_rules_cache
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        order = self.get_object(request, object_id)
        if order:
            try:
                order_content_type = ContentType.objects.get_for_model(order)
                available_templates = DocumentTemplate.objects.filter(
                    document_type__related_model=order_content_type, 
                    is_active=True
                )
                extra_context['available_document_templates'] = available_templates
                extra_context['current_object_id'] = object_id 
                extra_context['current_order_status_is_issued'] = (order.status == Order.STATUS_ISSUED)
            except ContentType.DoesNotExist:
                extra_context['available_document_templates'] = None
                messages.warning(request, "Не удалось определить тип контента для Заказа при поиске шаблонов документов.")
            except Exception as e:
                extra_context['available_document_templates'] = None
                messages.error(request, f"Ошибка при получении шаблонов документов: {str(e)}")
        
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def display_client_with_phone(self, obj):
        if obj.client:
            client_name = str(obj.client)
            phone_to_display = obj.client.phone
            client_url = reverse('admin:clients_client_change', args=[obj.client.pk])
            if phone_to_display:
                return format_html('<a href="{}">{} ({})</a>', client_url, client_name, phone_to_display)
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
        hex_color = self.status_colors_map.get(status_key, '#FFFFFF') 
        try:
            r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            text_color = '#000000' if luminance > 0.5 else '#FFFFFF'
        except: text_color = '#000000' 
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 5px 10px; border-radius: 4px;">{}</span>',
            hex_color, text_color, display_name,
        )
    colored_status.short_description = "Статус"
    colored_status.admin_order_field = 'status'

    def get_due_date_style(self, due_date):
        if not due_date: return None
        today = timezone.now().date()
        days_remaining = (due_date - today).days
        for rule in self.due_date_color_rules: 
            if rule.check_condition(days_remaining):
                hex_bg_color = rule.hex_color
                try:
                    r, g, b = int(hex_bg_color[1:3], 16), int(hex_bg_color[3:5], 16), int(hex_bg_color[5:7], 16)
                    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                    text_color = '#000000' if luminance > 0.5 else '#FFFFFF'
                except: text_color = '#000000'
                return {'background_color': hex_bg_color, 'text_color': text_color}
        return None

    def colored_due_date(self, obj):
        if obj.status == Order.STATUS_ISSUED:
            return "–" 
        if not obj.due_date: return "–" # Это также обработает тип "Определить", если due_date будет None
        
        date_str = obj.due_date.strftime("%d.%m.%Y")
        style = self.get_due_date_style(obj.due_date)
        if style:
            return format_html(
                '<span style="background-color: {}; color: {}; padding: 2px 5px; border-radius: 3px; white-space: nowrap;">{}</span>',
                style['background_color'], style['text_color'], date_str
            )
        return date_str
    colored_due_date.short_description = "Срок до"
    colored_due_date.admin_order_field = 'due_date'

    def get_fieldsets(self, request, obj=None):
        # ... (без изменений) ...
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
                ('Суммы и даты (информация)', {'fields': ('get_total_order_amount_display',) + tuple(date_info_fields_base)})
            )
            return fieldsets_config
        else: 
            new_order_main_fields = list(main_fields_tuple)
            if 'manager' in new_order_main_fields: new_order_main_fields.remove('manager')
            payment_closure_fieldset_fields_new = ['payment_method_on_closure']
            fieldsets_config_new = (
                (None, {'fields': tuple(new_order_main_fields)}),
                ('Оплата и закрытие заказа', {'fields': tuple(payment_closure_fieldset_fields_new)}),
                ('Суммы и даты (информация)', {'fields': ('get_total_order_amount_display',) + tuple(date_info_fields_base)})
            )
            return fieldsets_config_new


    def get_readonly_fields(self, request, obj=None):
        # Базовые поля, которые часто бывают readonly
        current_readonly_fields = ['created_at', 'updated_at', 'get_total_order_amount_display']
        
        # obj_to_check - это инстанс заказа, который отображается на форме
        # Для новой формы obj будет None. Для существующей - инстанс заказа.
        obj_to_check = obj

        # По умолчанию due_date делаем readonly. Оно станет редактируемым для "Продажи".
        current_readonly_fields.append('due_date')

        if obj_to_check and obj_to_check.pk: # Существующий заказ
            # Менеджер readonly в зависимости от прав
            can_edit_order_manager_group_name = "Редакторы ответственных в заказах" 
            user_can_edit_manager = request.user.is_superuser or request.user.groups.filter(name=can_edit_order_manager_group_name).exists()
            if not user_can_edit_manager:
                current_readonly_fields.append('manager')
            
            # Если заказ выдан, большинство полей становятся readonly
            if obj_to_check.status == Order.STATUS_ISSUED:
                current_readonly_fields.extend(['status', 'payment_method_on_closure', 'client', 'manager', 'performer', 'order_type'])
                # due_date уже добавлен в current_readonly_fields выше, так что для выданных он останется readonly
            else: # Заказ не выдан
                # Тип заказа readonly в зависимости от прав
                if not request.user.has_perm('orders.can_change_order_type_dynamically'):
                    current_readonly_fields.append('order_type')
                
                # --- НАЧАЛО ИЗМЕНЕНИЙ для due_date ---
                # Если тип заказа "Продажа", поле due_date должно быть редактируемым
                if obj_to_check.order_type and obj_to_check.order_type.name == OrderType.TYPE_SALE:
                    if 'due_date' in current_readonly_fields:
                        current_readonly_fields.remove('due_date')
                # Для типов "Ремонт" и "Определить" (и других) due_date остается readonly (т.к. был добавлен по умолчанию)
                # --- КОНЕЦ ИЗМЕНЕНИЙ для due_date ---
        else: # Новый заказ (obj is None)
            # Для новых заказов многие поля изначально readonly или имеют спец. логику
            current_readonly_fields.extend(['status', 'order_type', 'payment_method_on_closure', 'target_cash_register'])
            # due_date для нового заказа остается readonly (добавлен по умолчанию).
            # Он станет редактируемым для типа "Продажа" после первого сохранения, когда obj уже будет существовать.
            # Это приемлемый компромисс, т.к. тип заказа для нового объекта определяется после добавления инлайнов.
            
        return tuple(set(current_readonly_fields))


    def get_form(self, request, obj=None, **kwargs):
        # ... (без изменений) ...
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
        # ... (без изменений) ...
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
        # ... (без изменений) ...
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
        order_instance = form.instance 
        print(f"[OrderAdmin SaveRelated] НАЧАЛО для заказа ID: {order_instance.id}. Change: {change}")

        original_order_type_name_db = None
        original_due_date_db = None # Это due_date из БД до всех изменений на форме и инлайнах
        was_complex_before_save_db = False

        if change and order_instance.pk:
            try:
                # Загружаем состояние заказа из БД *до* сохранения инлайнов
                order_in_db = Order.objects.select_related('order_type').get(pk=order_instance.pk)
                original_order_type_name_db = order_in_db.order_type.name if order_in_db.order_type else None
                original_due_date_db = order_in_db.due_date
                if original_order_type_name_db == REPAIR_ORDER_TYPE_NAME:
                    was_complex_before_save_db = is_order_complex(order_in_db)
                print(f"[OrderAdmin SaveRelated] Состояние из БД ДО инлайнов: Тип='{original_order_type_name_db}', Срок={original_due_date_db}, Был комплексным={was_complex_before_save_db}")
            except Order.DoesNotExist:
                print(f"[OrderAdmin SaveRelated] ОШИБКА: Заказ ID {order_instance.pk} не найден в БД.")
                # Если не нашли в БД, берем значения из инстанса формы (хотя это не должно случиться для change=True)
                original_due_date_db = order_instance.due_date 
                if order_instance.order_type: original_order_type_name_db = order_instance.order_type.name
        elif not change: # Новый заказ
            print(f"[OrderAdmin SaveRelated] Новый заказ. Исходные данные: Тип=None, Срок=None, Был комплексным=False")
            # original_order_type_name_db и original_due_date_db остаются None
            # was_complex_before_save_db остается False
        
        # Сначала сохраняем инлайны, чтобы order_instance.service_items и product_items были актуальны
        super().save_related(request, form, formsets, change) 
        # Теперь order_instance (form.instance) содержит актуальные связанные объекты

        type_changed_by_determination = False
        # Определяем тип заказа на основе текущего состава (после сохранения инлайнов)
        if order_instance.determine_and_set_order_type():
            current_type_name_after_determination = order_instance.order_type.name if order_instance.order_type else None
            if current_type_name_after_determination != original_order_type_name_db:
                type_changed_by_determination = True
        
        print(f"[OrderAdmin SaveRelated] Заказ ID: {order_instance.id}. Тип ПОСЛЕ определения: {order_instance.order_type}. Тип изменился по сравнению с БД: {type_changed_by_determination}")

        # Рассчитываем/определяем новый due_date
        # order_instance.due_date здесь - это значение с формы, если поле было редактируемым,
        # или старое значение, если поле было readonly.
        new_due_date_calculated = determine_and_update_order_due_date(
            order_instance, # Передаем инстанс с уже обновленными инлайнами и типом
            not change,     # is_new_order
            was_complex_before_save_db,
            original_order_type_name_db 
        )
        
        fields_to_update_at_end = []
        if type_changed_by_determination:
            fields_to_update_at_end.append('order_type')
        
        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        if new_due_date_calculated is not None: # Сервис вернул конкретную дату
            if new_due_date_calculated != original_due_date_db:
                order_instance.due_date = new_due_date_calculated
                fields_to_update_at_end.append('due_date')
                print(f"[OrderAdmin SaveRelated] Заказ ID {order_instance.id}. Срок из БД: {original_due_date_db}, Новый РАССЧИТАННЫЙ/УСТАНОВЛЕННЫЙ срок: {new_due_date_calculated}")
            else:
                print(f"[OrderAdmin SaveRelated] Заказ ID {order_instance.id}. Срок из БД ({original_due_date_db}) уже соответствует расчетному ({new_due_date_calculated}). Обновление не требуется.")
        else: # new_due_date_calculated is None. Это может быть для "Определить", "Продажа" (очищено поле), или "Ремонт" (не менять)
            if order_instance.order_type and \
               (order_instance.order_type.name == OrderType.TYPE_UNDEFINED or order_instance.order_type.name == OrderType.TYPE_SALE):
                # Для "Определить" и "Продажа", если сервис вернул None, значит срок должен быть None.
                if original_due_date_db is not None: # Обновляем только если он действительно изменился на None
                    order_instance.due_date = None
                    fields_to_update_at_end.append('due_date')
                    print(f"[OrderAdmin SaveRelated] Заказ ID {order_instance.id} (тип {order_instance.order_type.name}). Срок из БД: {original_due_date_db}, Новый срок установлен в None.")
                else:
                    print(f"[OrderAdmin SaveRelated] Заказ ID {order_instance.id} (тип {order_instance.order_type.name}). Срок уже был None и остается None.")
            elif order_instance.order_type and order_instance.order_type.name == REPAIR_ORDER_TYPE_NAME:
                 # Для "Ремонта", если сервис вернул None, значит "не трогать существующий срок".
                 print(f"[OrderAdmin SaveRelated] Заказ ID {order_instance.id} (Ремонт). Сервис вернул None (не менять), due_date остается {original_due_date_db}.")
            else:
                # Случай, если тип не определен или какой-то другой, и сервис вернул None
                if original_due_date_db is not None:
                     order_instance.due_date = None
                     fields_to_update_at_end.append('due_date')
                     print(f"[OrderAdmin SaveRelated] Заказ ID {order_instance.id} (тип {order_instance.order_type.name if order_instance.order_type else 'N/A'}). Срок из БД: {original_due_date_db}, Новый срок установлен в None (fallback).")

        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        previous_db_status = getattr(request, '_current_order_previous_status_from_db_for_save_related', None)
        current_status_on_form = order_instance.status
        is_newly_issued_attempt = (
            order_instance.pk is not None and
            current_status_on_form == Order.STATUS_ISSUED and
            (previous_db_status is None or previous_db_status != Order.STATUS_ISSUED) 
        )
        operations_successful_issue = False

        if is_newly_issued_attempt:
            # ... (весь ваш блок try/except/finally для is_newly_issued_attempt остается ЗДЕСЬ БЕЗ ИЗМЕНЕНИЙ) ...
            # Важно: убедитесь, что order_instance.save() внутри этого блока включает 'order_type' и 'due_date',
            # если они есть в fields_to_update_at_end, чтобы они сохранились при выдаче.
            # Я добавил их в fields_to_save_on_issue.
            print(f"[OrderAdmin SaveRelated] Попытка выдачи заказа ID {order_instance.id}. Предыдущий статус в БД: {previous_db_status}, Текущий на форме: {current_status_on_form}")
            original_target_cash_register_id = order_instance.target_cash_register_id
            try:
                if not order_instance.payment_method_on_closure: raise ValidationError("Метод оплаты должен быть указан.")
                if order_instance.order_type and order_instance.order_type.name == REPAIR_ORDER_TYPE_NAME and not order_instance.performer: raise ValidationError(f"Исполнитель должен быть указан для '{REPAIR_ORDER_TYPE_NAME}'.")
                
                determined_cash_register_qs = CashRegister.objects.none()
                if order_instance.payment_method_on_closure == Order.ORDER_PAYMENT_METHOD_CASH: determined_cash_register_qs = CashRegister.objects.filter(is_default_for_cash=True, is_active=True)
                elif order_instance.payment_method_on_closure == Order.ORDER_PAYMENT_METHOD_CARD: determined_cash_register_qs = CashRegister.objects.filter(is_default_for_card=True, is_active=True)
                if not determined_cash_register_qs.exists(): raise ValidationError("Касса по умолчанию для выбранного метода оплаты не найдена.")
                if determined_cash_register_qs.count() > 1: raise ValidationError("Найдено несколько касс по умолчанию для выбранного метода оплаты.")
                determined_cash_register = determined_cash_register_qs.first()
                
                current_order_total = order_instance.calculate_total_amount()
                if not (current_order_total > Decimal('0.00')): raise ValidationError(f"Сумма заказа ({current_order_total}) должна быть > 0 для выдачи.")

                with transaction.atomic():
                    for item in order_instance.product_items.all():
                        calculate_and_assign_fifo_cost(item)
                        item.save(update_fields=['cost_price_at_sale'])
                    
                    for item in order_instance.product_items.all():
                        product_to_update = Product.objects.select_for_update().get(pk=item.product.pk)
                        if product_to_update.stock_quantity < item.quantity:
                            raise ValidationError(f"Недостаточно общего остатка товара '{product_to_update.name}' (в наличии: {product_to_update.stock_quantity}, требуется: {item.quantity})")
                        product_to_update.stock_quantity -= item.quantity
                        product_to_update.updated_at = timezone.now()
                        product_to_update.save(update_fields=['stock_quantity', 'updated_at'])
                    
                    order_instance.target_cash_register = determined_cash_register
                    order_instance.updated_at = timezone.now()
                    
                    fields_to_save_on_issue = ['target_cash_register', 'updated_at', 'status'] 
                    if 'order_type' in fields_to_update_at_end: fields_to_save_on_issue.append('order_type')
                    if 'due_date' in fields_to_update_at_end: fields_to_save_on_issue.append('due_date')
                    order_instance.save(update_fields=list(set(fields_to_save_on_issue))) # order_instance уже содержит обновленные order_type/due_date
                    print(f"[OrderAdmin SaveRelated] Заказ ID {order_instance.id} сохранен при выдаче. Поля: {fields_to_save_on_issue}")

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
                    
                    # --- БЛОК РАСЧЕТА ЗАРПЛАТЫ (без изменений) ---
                    earners_to_process = []
                    if order_instance.manager: earners_to_process.append({'employee_obj': order_instance.manager, 'role_key_for_rate': EmployeeRate.ROLE_MANAGER, 'role_verbose': 'Менеджер', 'salary_calc_role_context': SalaryCalculation.ROLE_CONTEXT_MANAGER})
                    if order_instance.performer: earners_to_process.append({'employee_obj': order_instance.performer, 'role_key_for_rate': EmployeeRate.ROLE_PERFORMER, 'role_verbose': 'Исполнитель', 'salary_calc_role_context': SalaryCalculation.ROLE_CONTEXT_PERFORMER})
                    any_salary_calculated_this_session = False
                    for earner_info in earners_to_process:
                        employee, role_key_for_rate, role_verbose_name, salary_calc_context_key = earner_info['employee_obj'], earner_info['role_key_for_rate'], earner_info['role_verbose'], earner_info['salary_calc_role_context']
                        employee_rate_instance = None
                        if order_instance.order_type:
                            try: employee_rate_instance = EmployeeRate.objects.get(employee=employee, order_type=order_instance.order_type, role_in_order=role_key_for_rate, is_active=True)
                            except EmployeeRate.DoesNotExist: pass
                            except EmployeeRate.MultipleObjectsReturned: employee_rate_instance = EmployeeRate.objects.filter(employee=employee, order_type=order_instance.order_type, role_in_order=role_key_for_rate, is_active=True).first()
                        if not employee_rate_instance: messages.warning(request, f"Активная ставка для {employee.first_name or employee.username} ({role_verbose_name}) для типа заказа '{order_instance.order_type}' не найдена. ЗП не начислена."); continue
                        salary_calc_obj, sc_created, sc_preexisting_non_zero_calc = self._get_or_create_salary_calculation(request, order_instance, employee, salary_calc_context_key, role_verbose_name)
                        if not sc_created: salary_calc_obj.service_details.all().delete(); salary_calc_obj.product_profit_details.all().delete(); salary_calc_obj.total_calculated_amount = Decimal('0.00')
                        current_session_earned_total_for_role = Decimal('0.00')
                        can_earn_from_services_for_role = not (order_instance.order_type.name == OrderType.TYPE_SALE and role_key_for_rate == EmployeeRate.ROLE_PERFORMER)
                        if can_earn_from_services_for_role and employee_rate_instance.service_percentage > Decimal('0.00'):
                            for service_item in order_instance.service_items.all():
                                base_amount = service_item.get_item_total()
                                if base_amount > Decimal('0.00'):
                                    earned = (base_amount * (employee_rate_instance.service_percentage / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                                    if earned > Decimal('0.00'): SalaryCalculationDetail.objects.create(salary_calculation=salary_calc_obj, order_service_item=service_item, source_description=service_item.service.name, base_amount_for_calc=base_amount, applied_percentage=employee_rate_instance.service_percentage, earned_amount=earned, detail_type=f"service_{role_key_for_rate}"); current_session_earned_total_for_role += earned
                        if employee_rate_instance.product_profit_percentage > Decimal('0.00'):
                            for item in order_instance.product_items.all():
                                if item.price_at_order is not None and item.cost_price_at_sale is not None and item.quantity > 0:
                                    profit = (item.price_at_order - item.cost_price_at_sale) * item.quantity
                                    if profit > Decimal('0.00'):
                                        earned = (profit * (employee_rate_instance.product_profit_percentage / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                                        if earned > Decimal('0.00'): ProductSalaryDetail.objects.create(salary_calculation=salary_calc_obj, order_product_item=item, product_name_snapshot=item.product.name, product_price_at_sale=item.price_at_order, product_cost_at_sale=item.cost_price_at_sale, profit_from_item=profit.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), applied_percentage=employee_rate_instance.product_profit_percentage, earned_amount=earned); current_session_earned_total_for_role += earned
                        if current_session_earned_total_for_role > Decimal('0.00') or sc_created or (not sc_created and sc_preexisting_non_zero_calc and salary_calc_obj.total_calculated_amount != current_session_earned_total_for_role):
                            salary_calc_obj.total_calculated_amount = current_session_earned_total_for_role.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP); rule_parts = []; service_details_exist = salary_calc_obj.service_details.filter(earned_amount__gt=0).exists(); product_details_exist = salary_calc_obj.product_profit_details.filter(earned_amount__gt=0).exists()
                            if service_details_exist: rule_parts.append(f"Услуги: {employee_rate_instance.service_percentage}%")
                            if product_details_exist: rule_parts.append(f"Приб.тов.: {employee_rate_instance.product_profit_percentage}%")
                            salary_calc_obj.applied_base_rule_info = f"Ставка для {role_verbose_name} ({employee.username}) в заказе типа '{order_instance.order_type.name if order_instance.order_type else 'N/A'}': {'; '.join(rule_parts) if rule_parts else 'Ставка применена, начислений нет'}."; salary_calc_obj.calculation_type = f"Сдельная ({role_verbose_name})"; salary_calc_obj.period_date = order_instance.updated_at.date(); salary_calc_obj.save(); any_salary_calculated_this_session = True
                            messages.success(request, f"Зарплата для {employee.first_name or employee.username} (Роль: {role_verbose_name}) по заказу #{order_instance.id} начислена/обновлена: {salary_calc_obj.total_calculated_amount} руб.")
                        elif not sc_created and not sc_preexisting_non_zero_calc and current_session_earned_total_for_role == Decimal('0.00'): messages.info(request, f"Для {employee.first_name or employee.username} (Роль: {role_verbose_name}) по заказу #{order_instance.id} в этой сессии начислений не произведено (сумма 0).")
                    if any_salary_calculated_this_session: order_instance.updated_at = timezone.now(); order_instance.save(update_fields=['updated_at'])
                    # --- КОНЕЦ БЛОКА РАСЧЕТА ЗАРПЛАТЫ ---
                    operations_successful_issue = True
                    print(f"[OrderAdmin SaveRelated] Все операции при выдаче заказа ID {order_instance.id} успешно завершены.")
            except ValidationError as e:
                messages.error(request, f"Не удалось завершить выдачу заказа №{order_instance.id}: {str(e)}")
            finally:
                if not operations_successful_issue and previous_db_status is not None:
                    if previous_db_status != Order.STATUS_ISSUED: 
                        Order.objects.filter(pk=order_instance.pk).update(
                            status=previous_db_status, 
                            updated_at=timezone.now(), 
                            target_cash_register_id=original_target_cash_register_id
                        )
                        form.instance.status = previous_db_status 
                        form.instance.target_cash_register_id = original_target_cash_register_id
                        messages.info(request, f"Статус заказа №{order_instance.id} возвращен на '{order_instance.get_status_display_for_key(previous_db_status)}'. Операции по выдаче отменены.")
        
        # Сохраняем измененный тип и/или срок, ЕСЛИ заказ НЕ выдавался успешно
        if not (is_newly_issued_attempt and operations_successful_issue):
            if fields_to_update_at_end: # Если есть что обновлять (тип или срок)
                print(f"[OrderAdmin SaveRelated] Финальное сохранение (вне блока успешной выдачи) для заказа ID {order_instance.id}. Поля: {fields_to_update_at_end}")
                if 'updated_at' not in fields_to_update_at_end:
                    fields_to_update_at_end.append('updated_at')
                order_instance.updated_at = timezone.now()
                
                # order_instance уже содержит обновленные значения order_type и due_date
                order_instance.save(update_fields=list(set(fields_to_update_at_end)))
                
                if 'order_type' in fields_to_update_at_end:
                    messages.info(request, f"Тип заказа №{order_instance.id} автоматически определен/обновлен на '{order_instance.order_type}'.")
                if 'due_date' in fields_to_update_at_end:
                    due_date_display = order_instance.due_date.strftime('%d.%m.%Y') if order_instance.due_date else "не установлен"
                    messages.info(request, f"Срок выполнения для заказа №{order_instance.id} обновлен на {due_date_display}.")
        
        print(f"[OrderAdmin SaveRelated] КОНЕЦ для заказа ID: {order_instance.id}")

    class Media:
        js = (
            'admin/js/jquery.init.js', 
            'orders/js/order_form_price_updater.js',
            'orders/js/order_fifo_updater.js',
            'orders/js/order_form_conditional_fields.js',
            'orders/js/adaptive_client_field.js', 
        )
        css = {
            'all': ('orders/css/admin_order_form.css',)
        }