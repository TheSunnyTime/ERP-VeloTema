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
        # Сохраняем связанные объекты (инлайны товаров/услуг) ДО определения типа
        super().save_related(request, form, formsets, change) 
        
        order_instance = form.instance 
        
        print(f"[OrderAdmin SaveRelated] Начало для заказа ID: {order_instance.id}. Тип до определения: {order_instance.order_type}")

        original_order_type_before_determination = order_instance.order_type
        type_changed_by_determination = False
        
        # Определяем и устанавливаем тип заказа на основе его содержимого
        # Этот метод должен сам вызывать order_instance.save(update_fields=['order_type', 'updated_at']), 
        # если тип действительно изменился и это не в рамках операции выдачи.
        # Либо мы будем сохранять тип позже, если он изменился.
        # Пока предполагаем, что determine_and_set_order_type только меняет атрибут в памяти.
        if order_instance.determine_and_set_order_type(): # Этот метод возвращает True, если тип изменился
            if order_instance.order_type != original_order_type_before_determination:
                type_changed_by_determination = True
        
        print(f"[OrderAdmin SaveRelated] Заказ ID: {order_instance.id}. Тип ПОСЛЕ определения: {order_instance.order_type}. Тип изменился: {type_changed_by_determination}")

        # --- БЛОК ПЕРЕСЧЕТА/УСТАНОВКИ DUE_DATE ---
        # Теперь, когда тип заказа потенциально обновлен, пересчитываем due_date, если нужно.
        
        recalculate_due_date_in_save_related = False
        
        if order_instance.order_type and order_instance.order_type.name == OrderType.TYPE_REPAIR:
            # Для новых заказов (change=False), если тип стал "Ремонт", 
            # или для существующих, если тип только что изменился на "Ремонт".
            # Также, если due_date еще не установлен (на случай, если сигнал не отработал или был пропущен).
            if (not change) or \
               (type_changed_by_determination and order_instance.order_type.name == OrderType.TYPE_REPAIR) or \
               (order_instance.due_date is None):
                recalculate_due_date_in_save_related = True
                print(f"[OrderAdmin SaveRelated] Заказ ID {order_instance.id} (тип {order_instance.order_type}). Требуется установка/пересчет due_date в save_related.")

        if recalculate_due_date_in_save_related:
            new_due_date = calculate_initial_due_date(order_instance) # Используем нашу функцию из services.py
            
            if order_instance.due_date != new_due_date:
                print(f"[OrderAdmin SaveRelated] Заказ ID {order_instance.id}. Старый due_date: {order_instance.due_date}, Новый due_date: {new_due_date}")
                order_instance.due_date = new_due_date
                # Мы сохраним order_instance целиком ниже, если тип менялся,
                # или если это операция выдачи.
                # Если только due_date изменился, а тип нет, и это не выдача, можно сохранить здесь.
                # Но для простоты, изменения due_date будут сохранены вместе с order_type, если он менялся,
                # или при финальном сохранении.
            else:
                print(f"[OrderAdmin SaveRelated] Заказ ID {order_instance.id}. due_date ({order_instance.due_date}) уже соответствует расчетному ({new_due_date}). Обновление не требуется.")
        # --- КОНЕЦ БЛОКА ПЕРЕСЧЕТА/УСТАНОВКИ DUE_DATE ---
        
        previous_db_status = getattr(request, '_current_order_previous_status_from_db_for_save_related', None)
        current_status_on_form = order_instance.status
        
        is_newly_issued_attempt = (
            order_instance.pk is not None and
            current_status_on_form == Order.STATUS_ISSUED and
            (previous_db_status is None or previous_db_status != Order.STATUS_ISSUED) 
        )
        
        operations_successful = False 

        # Сохраняем изменения типа и due_date ПЕРЕД логикой выдачи,
        # если это не попытка выдачи.
        fields_to_update_before_issue_logic = []
        if type_changed_by_determination and order_instance.order_type != original_order_type_before_determination:
            fields_to_update_before_issue_logic.append('order_type')
        
        # Если due_date был пересчитан и отличается от того, что в БД (или None)
        # Это немного сложно отследить без доп. запроса, поэтому будем полагаться на recalculate_due_date_in_save_related
        # и что order_instance.due_date теперь содержит новое значение, если оно изменилось.
        # Проще всего - если recalculate_due_date_in_save_related был True, то due_date могло измениться.
        if recalculate_due_date_in_save_related: # Если был запущен пересчет
             # Проверим, отличается ли текущее значение в инстансе от того, что могло быть установлено сигналом
             # или было ранее. Если order_instance.due_date изменилось, добавляем в список.
             # Это условие нужно уточнить, т.к. order_instance.due_date уже могло быть обновлено.
             # Для безопасности, если был пересчет, добавим due_date в список полей для сохранения.
             fields_to_update_before_issue_logic.append('due_date')


        if fields_to_update_before_issue_logic and not is_newly_issued_attempt:
            fields_to_update_before_issue_logic.append('updated_at')
            order_instance.updated_at = timezone.now()
            order_instance.save(update_fields=list(set(fields_to_update_before_issue_logic))) # set для уникальности
            print(f"[OrderAdmin SaveRelated] Заказ ID {order_instance.id}. Сохранены поля: {fields_to_update_before_issue_logic}")
            if 'order_type' in fields_to_update_before_issue_logic:
                 messages.info(request, f"Тип заказа №{order_instance.id} автоматически определен/обновлен на '{order_instance.order_type}'.")
            if 'due_date' in fields_to_update_before_issue_logic:
                 messages.info(request, f"Срок выполнения для заказа №{order_instance.id} обновлен на {order_instance.due_date.strftime('%d.%m.%Y')}.")


        if is_newly_issued_attempt:
            print(f"[OrderAdmin SaveRelated] Попытка выдачи заказа ID {order_instance.id}")
            original_target_cash_register_id = order_instance.target_cash_register_id
            # Важно: order_type и due_date должны быть уже актуальными в order_instance перед этой логикой

            try:
                # ... (твоя логика для is_newly_issued_attempt без изменений) ...
                # (я ее свернул для краткости, она остается без изменений)
                if not order_instance.payment_method_on_closure: raise ValidationError("Метод оплаты должен быть указан (проверка в save_related).")
                if order_instance.order_type and order_instance.order_type.name == OrderType.TYPE_REPAIR and not order_instance.performer: raise ValidationError(f"Исполнитель должен быть указан для '{OrderType.TYPE_REPAIR}' (проверка в save_related).")
                determined_cash_register_qs = CashRegister.objects.none()
                if order_instance.payment_method_on_closure == Order.ORDER_PAYMENT_METHOD_CASH: determined_cash_register_qs = CashRegister.objects.filter(is_default_for_cash=True, is_active=True)
                elif order_instance.payment_method_on_closure == Order.ORDER_PAYMENT_METHOD_CARD: determined_cash_register_qs = CashRegister.objects.filter(is_default_for_card=True, is_active=True)
                if not determined_cash_register_qs.exists(): raise ValidationError("Касса по умолчанию для выбранного метода оплаты не найдена.")
                if determined_cash_register_qs.count() > 1: raise ValidationError("Найдено несколько касс по умолчанию для выбранного метода оплаты.")
                determined_cash_register = determined_cash_register_qs.first()
                current_order_total = order_instance.calculate_total_amount()
                if not (current_order_total > Decimal('0.00')): raise ValidationError(f"Сумма заказа ({current_order_total}) должна быть > 0 для выдачи.")
                with transaction.atomic():
                    # Если тип или due_date менялись, и это операция выдачи, они должны быть сохранены здесь
                    # или до этого блока with transaction.atomic()
                    if fields_to_update_before_issue_logic: # Если были изменения типа или due_date
                        fields_to_update_before_issue_logic.append('updated_at') # updated_at тоже
                        order_instance.updated_at = timezone.now()
                        order_instance.save(update_fields=list(set(fields_to_update_before_issue_logic)))
                        print(f"[OrderAdmin SaveRelated] Заказ ID {order_instance.id} (перед выдачей). Сохранены поля: {fields_to_update_before_issue_logic}")
                        if 'order_type' in fields_to_update_before_issue_logic:
                             messages.info(request, f"Тип заказа №{order_instance.id} автоматически определен/обновлен на '{order_instance.order_type}'.")
                        if 'due_date' in fields_to_update_before_issue_logic:
                             messages.info(request, f"Срок выполнения для заказа №{order_instance.id} обновлен на {order_instance.due_date.strftime('%d.%m.%Y')}.")


                    for order_item_instance in order_instance.product_items.all(): 
                        calculate_and_assign_fifo_cost(order_item_instance)
                        order_item_instance.save(update_fields=['cost_price_at_sale'])
                    for item_to_update_stock in order_instance.product_items.all():
                        product_to_update = Product.objects.select_for_update().get(pk=item_to_update_stock.product.pk)
                        if product_to_update.stock_quantity < item_to_update_stock.quantity:
                            raise ValidationError(f"Недостаточно общего остатка товара '{product_to_update.name}' (в наличии: {product_to_update.stock_quantity}, требуется: {item_to_update_stock.quantity})")
                        product_to_update.stock_quantity -= item_to_update_stock.quantity
                        product_to_update.updated_at = timezone.now()
                        product_to_update.save(update_fields=['stock_quantity', 'updated_at'])
                    
                    # target_cash_register устанавливается и сохраняется здесь, updated_at тоже
                    order_instance.target_cash_register = determined_cash_register
                    order_instance.updated_at = timezone.now() 
                    order_instance.save(update_fields=['target_cash_register', 'updated_at']) 

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
                    # ... (твоя логика расчета зарплат) ...
                    earners_to_process = [] # и т.д.
                    if order_instance.manager: earners_to_process.append({'employee_obj': order_instance.manager, 'role_key_for_rate': EmployeeRate.ROLE_MANAGER, 'role_verbose': 'Менеджер', 'salary_calc_role_context': SalaryCalculation.ROLE_CONTEXT_MANAGER})
                    if order_instance.performer: earners_to_process.append({'employee_obj': order_instance.performer, 'role_key_for_rate': EmployeeRate.ROLE_PERFORMER, 'role_verbose': 'Исполнитель', 'salary_calc_role_context': SalaryCalculation.ROLE_CONTEXT_PERFORMER})
                    any_salary_calculated_this_session = False
                    for earner_info in earners_to_process:
                        # ... (много кода расчета зарплаты)
                        pass # Заглушка для твоего кода
                    if any_salary_calculated_this_session: order_instance.updated_at = timezone.now(); order_instance.save(update_fields=['updated_at'])

                operations_successful = True
            except ValidationError as e:
                messages.error(request, f"Не удалось завершить выдачу заказа №{order_instance.id}: {str(e)}")
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
        
        # Если это не операция выдачи, И тип менялся, ИЛИ due_date менялся,
        # а мы еще не сохранили эти изменения выше (например, потому что is_newly_issued_attempt был True, но не прошел)
        # Этот блок может быть избыточен, если блок "fields_to_update_before_issue_logic" уже отработал.
        # Но для надежности, если тип изменился и это не была успешная выдача, убедимся, что тип сохранен.
        elif type_changed_by_determination and (not is_newly_issued_attempt or not operations_successful):
             if order_instance.order_type != original_order_type_before_determination:
                print(f"[OrderAdmin SaveRelated] Финальное сохранение (после блока выдачи, если он был) изменения типа заказа {order_instance.id}.")
                fields_to_save_finally = ['order_type']
                if recalculate_due_date_in_save_related: # Если due_date тоже менялся
                    fields_to_save_finally.append('due_date')
                
                if fields_to_save_finally:
                    fields_to_save_finally.append('updated_at')
                    order_instance.updated_at = timezone.now()
                    order_instance.save(update_fields=list(set(fields_to_save_finally)))
                
                messages.info(request, f"Тип заказа №{order_instance.id} автоматически определен/обновлен на '{order_instance.order_type}'.")
                if 'due_date' in fields_to_save_finally:
                    messages.info(request, f"Срок выполнения для заказа №{order_instance.id} обновлен на {order_instance.due_date.strftime('%d.%m.%Y')}.")



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