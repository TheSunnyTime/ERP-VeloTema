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
from uiconfig.models import OrderStatusColor

from ..models import Order, OrderType
from ..forms import OrderAdminForm
from ..fifo_logic import calculate_and_assign_fifo_cost

from .order_inlines_admin import OrderProductItemInline, OrderServiceItemInline

from salary_management.models import EmployeeRate, SalaryCalculation, SalaryCalculationDetail, ProductSalaryDetail
from utils.models import DocumentTemplate # Убедись, что импорт есть
from products.models import Product
from cash_register.models import CashRegister, CashTransaction


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    form = OrderAdminForm
    list_display = (
        'id',
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
        'status', 'order_type', 'created_at', 'manager', 'performer',
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
    change_form_template = 'admin/orders/order/change_form_with_documents.html' # <--- РАСКОММЕНТИРОВАНО

    def __init__(self, model, admin_site):
        # ... (код без изменений) ...
        super().__init__(model, admin_site)
        self.status_colors_map = {
            color_setting.status_key: color_setting.hex_color
            for color_setting in OrderStatusColor.objects.all()
        }

    def display_client_with_phone(self, obj):
        # ... (код без изменений) ...
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
        # ... (код без изменений) ...
        if obj.manager:
            return obj.manager.first_name if obj.manager.first_name else obj.manager.username
        return "N/A"
    display_manager_name.short_description = "Менеджер"
    display_manager_name.admin_order_field = 'manager__first_name'

    def display_performer_name(self, obj):
        # ... (код без изменений) ...
        if obj.performer:
            return obj.performer.first_name if obj.performer.first_name else obj.performer.username
        return "N/A"
    display_performer_name.short_description = "Исполнитель"
    display_performer_name.admin_order_field = 'performer__first_name'

    def get_total_order_amount_display(self, obj):
        # ... (код без изменений) ...
        if obj.pk: return obj.calculate_total_amount()
        return Decimal('0.00')
    get_total_order_amount_display.short_description = "Общая сумма заказа"

    def colored_status(self, obj):
        # ... (код без изменений) ...
        status_key = obj.status
        display_name = obj.get_status_display()
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

    def get_fieldsets(self, request, obj=None):
        # ... (код без изменений) ...
        main_fields_tuple = ('client', 'manager', 'performer', 'order_type', 'repaired_item', 'status', 'notes')
        payment_closure_fieldset_fields = ['payment_method_on_closure']
        if request.user.is_superuser or request.user.has_perm('orders.can_view_target_cash_register'):
            payment_closure_fieldset_fields.append('target_cash_register')
        if obj:
            current_main_fields = list(main_fields_tuple)
            fieldsets_config = (
                (None, {'fields': tuple(current_main_fields)}),
                ('Оплата и закрытие заказа', {'fields': tuple(payment_closure_fieldset_fields)}),
                ('Суммы и даты (информация)', {'fields': ('get_total_order_amount_display', 'created_at', 'updated_at')}),
            )
            return fieldsets_config
        else:
            new_order_main_fields = list(main_fields_tuple)
            if 'manager' in new_order_main_fields: new_order_main_fields.remove('manager')
            payment_closure_fieldset_fields_new = ['payment_method_on_closure']
            fieldsets_config_new = (
                (None, {'fields': tuple(new_order_main_fields)}),
                ('Оплата и закрытие заказа', {'fields': tuple(payment_closure_fieldset_fields_new)}),
                ('Суммы и даты (информация)', {'fields': ('get_total_order_amount_display',)}),
            )
            return fieldsets_config_new

    def get_readonly_fields(self, request, obj=None):
        # ... (код без изменений) ...
        base_readonly = ['created_at', 'updated_at', 'get_total_order_amount_display']
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
        # ... (код без изменений) ...
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
        # ... (код без изменений) ...
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
        # ... (код без изменений) ...
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
        
        original_order_type_before_determination = order_instance.order_type
        type_changed_by_determination = False
        if order_instance.determine_and_set_order_type(): 
            if order_instance.order_type != original_order_type_before_determination:
                type_changed_by_determination = True
                # Сообщение об изменении типа будет выведено позже, если операция успешна
        
        previous_db_status = getattr(request, '_current_order_previous_status_from_db_for_save_related', None)
        current_status_on_form = order_instance.status
        
        is_newly_issued_attempt = (
            order_instance.pk is not None and
            current_status_on_form == Order.STATUS_ISSUED and
            (previous_db_status is None or previous_db_status != Order.STATUS_ISSUED) 
        )
        
        print(f"[SAVE_RELATED DEBUG] Order ID: {order_instance.id}")
        print(f"[SAVE_RELATED DEBUG] previous_db_status: {previous_db_status}")
        print(f"[SAVE_RELATED DEBUG] current_status_on_form: {current_status_on_form}")
        print(f"[SAVE_RELATED DEBUG] is_newly_issued_attempt: {is_newly_issued_attempt}")

        operations_successful = False # Инициализируем здесь

        if is_newly_issued_attempt:
            print(f"[SAVE_RELATED DEBUG] Attempting 'issued' specific operations for order {order_instance.id}")
            original_target_cash_register_id = order_instance.target_cash_register_id

            try:
                print("[SAVE_RELATED DEBUG] Inside 'is_newly_issued_attempt' TRY block")
                
                # Проверки, которые должны были быть в Order.clean() (оставляем для отладки, если они там не сработали)
                if not order_instance.payment_method_on_closure: raise ValidationError("Метод оплаты должен быть указан (проверка в save_related).")
                if order_instance.order_type and order_instance.order_type.name == OrderType.TYPE_REPAIR and not order_instance.performer: raise ValidationError(f"Исполнитель должен быть указан для '{OrderType.TYPE_REPAIR}' (проверка в save_related).")
                
                determined_cash_register_qs = CashRegister.objects.none()
                if order_instance.payment_method_on_closure == Order.ORDER_PAYMENT_METHOD_CASH: determined_cash_register_qs = CashRegister.objects.filter(is_default_for_cash=True, is_active=True)
                elif order_instance.payment_method_on_closure == Order.ORDER_PAYMENT_METHOD_CARD: determined_cash_register_qs = CashRegister.objects.filter(is_default_for_card=True, is_active=True)
                if not determined_cash_register_qs.exists(): raise ValidationError("Касса по умолчанию не найдена.")
                if determined_cash_register_qs.count() > 1: raise ValidationError("Найдено несколько касс по умолчанию.")
                determined_cash_register = determined_cash_register_qs.first(); print(f"[SAVE_RELATED DEBUG] Determined cash register: {determined_cash_register}")
                
                current_order_total = order_instance.calculate_total_amount()
                if not (current_order_total > Decimal('0.00')): raise ValidationError(f"Сумма заказа ({current_order_total}) должна быть > 0 для выдачи."); print(f"[SAVE_RELATED DEBUG] Order total: {current_order_total}")
                
                with transaction.atomic():
                    print("[SAVE_RELATED DEBUG] Inside transaction.atomic()")
                    for item_idx, order_item_instance in enumerate(order_instance.product_items.all()): print(f"[SAVE_RELATED DEBUG] Processing FIFO for item {item_idx + 1}: {order_item_instance.product.name}"); calculate_and_assign_fifo_cost(order_item_instance); order_item_instance.save(update_fields=['cost_price_at_sale']); print(f"[SAVE_RELATED DEBUG] FIFO cost_price_at_sale for {order_item_instance.product.name}: {order_item_instance.cost_price_at_sale}")
                    for item_idx, item_to_update_stock in enumerate(order_instance.product_items.all()): print(f"[SAVE_RELATED DEBUG] Updating stock for item {item_idx + 1}: {item_to_update_stock.product.name}"); product_to_update = Product.objects.select_for_update().get(pk=item_to_update_stock.product.pk);_ = product_to_update.stock_quantity < item_to_update_stock.quantity and (_ for _ in ()).throw(ValidationError(f"Недостаточно общего остатка товара '{product_to_update.name}' (в наличии: {product_to_update.stock_quantity}, требуется: {item_to_update_stock.quantity})")); product_to_update.stock_quantity -= item_to_update_stock.quantity; product_to_update.updated_at = timezone.now(); product_to_update.save(update_fields=['stock_quantity', 'updated_at']); print(f"[SAVE_RELATED DEBUG] Stock updated for {product_to_update.name}, new stock: {product_to_update.stock_quantity}")
                    
                    # Сохраняем target_cash_register и updated_at для заказа
                    # Статус 'Выдан' уже сохранен в save_model.
                    order_instance.target_cash_register = determined_cash_register # Устанавливаем перед сохранением
                    order_instance.updated_at = timezone.now()
                    order_instance.save(update_fields=['target_cash_register', 'updated_at']) 
                    print(f"[SAVE_RELATED DEBUG] Order target_cash_register and updated_at saved. Target cash: {determined_cash_register}")

                    if not CashTransaction.objects.filter(order=order_instance, transaction_type=CashTransaction.TRANSACTION_TYPE_INCOME).exists(): CashTransaction.objects.create(cash_register=order_instance.target_cash_register, transaction_type=CashTransaction.TRANSACTION_TYPE_INCOME, payment_method=order_instance.payment_method_on_closure, amount=current_order_total, employee=order_instance.manager, order=order_instance, description=f"Оплата по заказу №{order_instance.id} (статус Выдан)"); print("[SAVE_RELATED DEBUG] Cash transaction created.")
                    
                    # --- НАЧАЛО БЛОКА РАСЧЕТА ЗАРПЛАТЫ (ВСТАВЬ СЮДА СВОЙ ПОЛНЫЙ КОД С ОТЛАДОЧНЫМИ PRINT) ---
                    print(f"[SAVE_RELATED DEBUG] Starting Salary calculation block for order {order_instance.id}...")
                    
                    # Пример структуры с отладочными print'ами (замени на свой актуальный код):
                    earners_to_process = []
                    if order_instance.manager:
                        print(f"[SALARY DEBUG] Adding manager {order_instance.manager.username} to earners_to_process.")
                        earners_to_process.append({
                            'employee_obj': order_instance.manager, 
                            'role_key_for_rate': EmployeeRate.ROLE_MANAGER,
                            'role_verbose': 'Менеджер',
                            'salary_calc_role_context': SalaryCalculation.ROLE_CONTEXT_MANAGER
                        })
                    else:
                        print("[SALARY DEBUG] No manager assigned to order for salary calculation.")
                    
                    if order_instance.performer:
                        print(f"[SALARY DEBUG] Adding performer {order_instance.performer.username} to earners_to_process.")
                        earners_to_process.append({
                            'employee_obj': order_instance.performer,
                            'role_key_for_rate': EmployeeRate.ROLE_PERFORMER,
                            'role_verbose': 'Исполнитель',
                            'salary_calc_role_context': SalaryCalculation.ROLE_CONTEXT_PERFORMER
                        })
                    else:
                        print("[SALARY DEBUG] No performer assigned to order for salary calculation.")
                    
                    any_salary_calculated_this_session = False
                    for earner_info_idx, earner_info in enumerate(earners_to_process):
                        employee = earner_info['employee_obj']
                        role_key_for_rate = earner_info['role_key_for_rate']
                        role_verbose_name = earner_info['role_verbose']
                        salary_calc_context_key = earner_info['salary_calc_role_context']
                        print(f"[SALARY DEBUG {earner_info_idx+1}] Processing for: {employee.username}, Role: {role_verbose_name}, Order Type: {order_instance.order_type}")
                        employee_rate_instance = None
                        if order_instance.order_type:
                            try:
                                employee_rate_instance = EmployeeRate.objects.get(employee=employee, order_type=order_instance.order_type, role_in_order=role_key_for_rate, is_active=True)
                                print(f"[SALARY DEBUG {earner_info_idx+1}] Found active rate: ID {employee_rate_instance.id}, Product Profit %: {employee_rate_instance.product_profit_percentage}, Service %: {employee_rate_instance.service_percentage}")
                            except EmployeeRate.DoesNotExist: print(f"[SALARY DEBUG {earner_info_idx+1}] Active rate for {employee.username} (Role: {role_verbose_name}, Order Type: {order_instance.order_type}) NOT FOUND.")
                            except EmployeeRate.MultipleObjectsReturned: print(f"[SALARY DEBUG {earner_info_idx+1}] Multiple active rates found for {employee.username}. Using first one."); employee_rate_instance = EmployeeRate.objects.filter(employee=employee, order_type=order_instance.order_type, role_in_order=role_key_for_rate, is_active=True).first()
                        else: print(f"[SALARY DEBUG {earner_info_idx+1}] Order type is not set, cannot find rate.")
                        if not employee_rate_instance: messages.warning(request, f"Активная ставка для {employee} ({role_verbose_name}) для типа заказа '{order_instance.order_type}' не найдена. ЗП не начислена."); continue
                        salary_calc_obj, sc_created, sc_preexisting_non_zero_calc = self._get_or_create_salary_calculation(request, order_instance, employee, salary_calc_context_key, role_verbose_name)
                        if not sc_created: print(f"[SALARY DEBUG {earner_info_idx+1}] Old SalaryCalculation details cleared for ID: {salary_calc_obj.id}"); salary_calc_obj.service_details.all().delete(); salary_calc_obj.product_profit_details.all().delete(); salary_calc_obj.total_calculated_amount = Decimal('0.00')
                        current_session_earned_total_for_role = Decimal('0.00')
                        if employee_rate_instance.product_profit_percentage > Decimal('0.00'):
                            print(f"[SALARY DEBUG {earner_info_idx+1}] Calculating product profit for {employee.username}, %: {employee_rate_instance.product_profit_percentage}")
                            for item_idx_prod, item in enumerate(order_instance.product_items.all()):
                                if item.price_at_order is not None and item.cost_price_at_sale is not None and item.quantity > 0:
                                    profit_per_unit = item.price_at_order - item.cost_price_at_sale; total_profit_for_line = profit_per_unit * item.quantity
                                    print(f"[SALARY DEBUG {earner_info_idx+1}] Product item {item_idx_prod+1} '{item.product.name}': Price={item.price_at_order}, Cost={item.cost_price_at_sale}, Qty={item.quantity}, ProfitLine={total_profit_for_line}")
                                    if total_profit_for_line > Decimal('0.00'):
                                        earned_from_profit = (total_profit_for_line * (employee_rate_instance.product_profit_percentage / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                                        if earned_from_profit > Decimal('0.00'): ProductSalaryDetail.objects.create(salary_calculation=salary_calc_obj, order_product_item=item, product_name_snapshot=item.product.name, product_price_at_sale=item.price_at_order, product_cost_at_sale=item.cost_price_at_sale, profit_from_item=total_profit_for_line.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), applied_percentage=employee_rate_instance.product_profit_percentage, earned_amount=earned_from_profit); current_session_earned_total_for_role += earned_from_profit; print(f"[SALARY DEBUG {earner_info_idx+1}] +{earned_from_profit} from product '{item.product.name}'")
                        can_earn_from_services = order_instance.order_type and order_instance.order_type.name != OrderType.TYPE_SALE
                        if can_earn_from_services and employee_rate_instance.service_percentage > Decimal('0.00'):
                            print(f"[SALARY DEBUG {earner_info_idx+1}] Calculating service payment for {employee.username}, %: {employee_rate_instance.service_percentage}")
                            for item_idx_serv, service_item in enumerate(order_instance.service_items.all()):
                                base_amount = service_item.get_item_total()
                                print(f"[SALARY DEBUG {earner_info_idx+1}] Service item {item_idx_serv+1} '{service_item.service.name}': BaseAmount={base_amount}")
                                if base_amount is not None and base_amount > Decimal('0.00'):
                                    earned_from_service = (base_amount * (employee_rate_instance.service_percentage / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                                    if earned_from_service > Decimal('0.00'): SalaryCalculationDetail.objects.create(salary_calculation=salary_calc_obj, order_service_item=service_item, source_description=service_item.service.name, base_amount_for_calc=base_amount, applied_percentage=employee_rate_instance.service_percentage, earned_amount=earned_from_service, detail_type=f"service_{role_key_for_rate}"); current_session_earned_total_for_role += earned_from_service; print(f"[SALARY DEBUG {earner_info_idx+1}] +{earned_from_service} from service '{service_item.service.name}'")
                        print(f"[SALARY DEBUG {earner_info_idx+1}] Total earned for role in this session: {current_session_earned_total_for_role}")
                        if current_session_earned_total_for_role > Decimal('0.00') or sc_created or (not sc_created and sc_preexisting_non_zero_calc and salary_calc_obj.total_calculated_amount != current_session_earned_total_for_role):
                            salary_calc_obj.total_calculated_amount = current_session_earned_total_for_role.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP); rule_parts = []; service_details_exist = salary_calc_obj.service_details.filter(earned_amount__gt=0).exists(); product_details_exist = salary_calc_obj.product_profit_details.filter(earned_amount__gt=0).exists()
                            if service_details_exist: rule_parts.append(f"Услуги: {employee_rate_instance.service_percentage}%")
                            if product_details_exist: rule_parts.append(f"Приб.тов.: {employee_rate_instance.product_profit_percentage}%")
                            salary_calc_obj.applied_base_rule_info = f"Ставка для {role_verbose_name} ({employee.username}) в заказе типа '{order_instance.order_type.name if order_instance.order_type else 'N/A'}': {'; '.join(rule_parts) if rule_parts else 'Ставка применена, начислений нет'}."; salary_calc_obj.calculation_type = f"Сдельная ({role_verbose_name})"; salary_calc_obj.period_date = order_instance.updated_at.date(); salary_calc_obj.save(); any_salary_calculated_this_session = True
                            print(f"[SALARY DEBUG {earner_info_idx+1}] SAVED SalaryCalculation for {employee.username}, Amount: {salary_calc_obj.total_calculated_amount}, Info: {salary_calc_obj.applied_base_rule_info}")
                            messages.success(request, f"Зарплата для {employee} (Роль: {role_verbose_name}) по заказу #{order_instance.id} начислена/обновлена: {salary_calc_obj.total_calculated_amount} руб.")
                        elif not sc_created and not sc_preexisting_non_zero_calc and current_session_earned_total_for_role == Decimal('0.00'): messages.info(request, f"Для {employee} (Роль: {role_verbose_name}) по заказу #{order_instance.id} в этой сессии начислений не произведено.")
                    if any_salary_calculated_this_session: print("[SALARY DEBUG] Salaries were calculated/updated, updating order's updated_at."); order_instance.updated_at = timezone.now(); order_instance.save(update_fields=['updated_at'])
                    else: print("[SALARY DEBUG] No salaries were calculated/updated in this session.")
                    # --- КОНЕЦ БЛОКА РАСЧЕТА ЗАРПЛАТЫ ---

                operations_successful = True
                print("[SAVE_RELATED DEBUG] All 'issued' operations successful within transaction (including salary).")

            except ValidationError as e:
                print(f"[SAVE_RELATED DEBUG] ValidationError caught in 'is_newly_issued_attempt': {str(e)}")
                messages.error(request, f"Не удалось завершить выдачу заказа №{order_instance.id}: {str(e)}")
                
            finally:
                print(f"[SAVE_RELATED DEBUG] Finally block. operations_successful: {operations_successful}, previous_db_status: {previous_db_status}")
                if not operations_successful and previous_db_status is not None:
                    if previous_db_status != Order.STATUS_ISSUED:
                        print(f"[SAVE_RELATED DEBUG] Reverting status in DB from '{order_instance.status}' to '{previous_db_status}' for order {order_instance.id}")
                        Order.objects.filter(pk=order_instance.pk).update(
                            status=previous_db_status, 
                            updated_at=timezone.now(),
                            target_cash_register_id=original_target_cash_register_id 
                        )
                        form.instance.status = previous_db_status 
                        form.instance.target_cash_register_id = original_target_cash_register_id
                        messages.info(request, f"Статус заказа №{order_instance.id} возвращен на '{order_instance.get_status_display_for_key(previous_db_status)}'. Операции по выдаче отменены.")
                    else:
                        print(f"[SAVE_RELATED DEBUG] Status not reverted: previous_db_status was already 'issued'. Current form status on error: {form.instance.status}")
                elif operations_successful:
                     print("[SAVE_RELATED DEBUG] Operations were successful, no status revert needed.")
                elif previous_db_status is None:
                     print("[SAVE_RELATED DEBUG] previous_db_status is None (new object?), cannot revert status based on it.")
        
        else: # if not is_newly_issued_attempt:
            print(f"[SAVE_RELATED DEBUG] 'is_newly_issued_attempt' is False. No 'issued' specific operations for order {order_instance.id}.")
        
        # Логика сохранения измененного типа заказа (если это не была неудачная попытка выдачи)
        if type_changed_by_determination:
            # Сохраняем тип, если:
            # 1. Это не была попытка выдачи (is_newly_issued_attempt is False)
            # 2. ИЛИ это была УСПЕШНАЯ попытка выдачи (is_newly_issued_attempt is True AND operations_successful is True)
            if not is_newly_issued_attempt or (is_newly_issued_attempt and operations_successful):
                # Убедимся, что тип действительно изменился по сравнению с тем, что было до determine_and_set_order_type
                if order_instance.order_type != original_order_type_before_determination:
                    print(f"[SAVE_RELATED DEBUG] Final save for order type change for order {order_instance.id}. Original type: {original_order_type_before_determination}, New type: {order_instance.order_type}")
                    order_instance.updated_at = timezone.now() 
                    order_instance.save(update_fields=['order_type', 'updated_at'])
                    messages.info(request, f"Тип заказа №{order_instance.id} автоматически определен/обновлен на '{order_instance.order_type}'.") # Показываем сообщение здесь
    
    # ... (остальные методы, change_view, Media) ...
    def change_view(self, request, object_id, form_url='', extra_context=None):
        # ... (твой код change_view без отладочных print) ...
        original_extra_context = extra_context.copy() if extra_context else {}
        order = self.get_object(request, object_id)
        if order:
            try:
                order_content_type = ContentType.objects.get_for_model(order)
                available_templates = DocumentTemplate.objects.filter(document_type__related_model=order_content_type, is_active=True)
                original_extra_context['available_document_templates'] = available_templates
                original_extra_context['current_object_id'] = object_id
                original_extra_context['current_order_status_is_issued'] = (order.status == Order.STATUS_ISSUED)
            except ContentType.DoesNotExist:
                original_extra_context['available_document_templates'] = None; messages.warning(request, "Не удалось определить тип контента для Заказа.")
            except Exception as e:
                original_extra_context['available_document_templates'] = None; messages.error(request, f"Ошибка при получении шаблонов документов: {str(e)}")
        return super().change_view(request, object_id, form_url, extra_context=original_extra_context)


    class Media:
        js = (
            'admin/js/jquery.init.js',
            'orders/js/order_form_price_updater.js',
            'orders/js/order_form_conditional_fields.js',
        )
        css = {
            'all': ('orders/css/admin_order_form.css',)
        }