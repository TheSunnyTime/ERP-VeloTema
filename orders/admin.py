# F:\CRM 2.0\ERP\orders\admin.py
from django.contrib import admin, messages
from django.contrib.auth.models import User, Group 
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from decimal import Decimal, ROUND_HALF_UP
from django.contrib.contenttypes.models import ContentType
# from django.utils.html import format_html # Раскомментируй, если будешь использовать

from .models import Service, Order, OrderType, OrderProductItem, OrderServiceItem
from .forms import BaseOrderProductItemFormSet, OrderAdminForm # Убедись, что OrderAdminForm существует и актуальна

# Импорты из других приложений
from salary_management.models import (
    EmployeeRate, 
    SalaryCalculation, 
    SalaryCalculationDetail, 
    ProductSalaryDetail
)
from utils.models import DocumentTemplate # Убедись, что модель DocumentTemplate импортируется правильно
from products.models import Product 
from cash_register.models import CashTransaction, CashRegister

# --- Модификация отображения User ---
if not hasattr(User, '__str_original_for_crm__'): 
    User.__str_original_for_crm__ = User.__str__ 
    def user_custom_display_name(self):
        if self.first_name:
            return self.first_name
        return self.username
    User.add_to_class("__str__", user_custom_display_name)
# --- Конец ---

@admin.register(OrderType)
class OrderTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)
    ordering = ['name']

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'price')
    search_fields = ('name',)
    ordering = ['name']

def get_parent_order_from_request(request, obj_inline=None):
    if obj_inline and obj_inline.pk and hasattr(obj_inline, 'order'):
        return obj_inline.order
    resolver_match = request.resolver_match
    if resolver_match and 'object_id' in resolver_match.kwargs:
        parent_order_id = resolver_match.kwargs['object_id']
        if parent_order_id:
            try:
                return Order.objects.get(pk=parent_order_id)
            except Order.DoesNotExist:
                return None
    return None

class OrderProductItemInline(admin.TabularInline):
    model = OrderProductItem
    formset = BaseOrderProductItemFormSet
    extra = 0
    autocomplete_fields = ['product']
    fields = ('product', 'get_current_stock', 'quantity', 
              'price_at_order', 'cost_price_at_sale', 'display_item_total')
    
    def get_current_stock(self, obj):
        if obj.product: return obj.product.stock_quantity
        return "N/A"
    get_current_stock.short_description = "На складе (тек.)"

    def display_item_total(self, obj):
        if obj.pk: return obj.get_item_total()
        return Decimal('0.00')
    display_item_total.short_description = "Сумма по строке"

    def get_readonly_fields(self, request, obj=None):
        readonly = ['get_current_stock', 'display_item_total', 'cost_price_at_sale']
        if not request.user.is_superuser: 
            readonly.append('price_at_order')
        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status == Order.STATUS_ISSUED:
            readonly.extend(['product', 'quantity', 'price_at_order'])
        return tuple(set(readonly))

    def has_add_permission(self, request, obj=None):
        parent_order = get_parent_order_from_request(request)
        if parent_order and parent_order.status == Order.STATUS_ISSUED: return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status == Order.STATUS_ISSUED: return False
        return super().has_delete_permission(request, obj)

class OrderServiceItemInline(admin.TabularInline):
    model = OrderServiceItem
    extra = 0
    autocomplete_fields = ['service']
    fields = ('service', 'quantity', 'price_at_order', 'display_item_total')

    def display_item_total(self, obj):
        if obj.pk: return obj.get_item_total()
        return Decimal('0.00')
    display_item_total.short_description = "Сумма по строке"

    def get_readonly_fields(self, request, obj=None):
        readonly = ['display_item_total']
        if not request.user.is_superuser: 
            readonly.append('price_at_order')
        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status == Order.STATUS_ISSUED:
            readonly.extend(['service', 'quantity', 'price_at_order'])
        return tuple(set(readonly))

    def has_add_permission(self, request, obj=None):
        parent_order = get_parent_order_from_request(request)
        if parent_order and parent_order.status == Order.STATUS_ISSUED: return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status == Order.STATUS_ISSUED: return False
        return super().has_delete_permission(request, obj)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    form = OrderAdminForm
    list_display = (
        'id', 'client', 
        'display_manager_name',       
        'display_performer_name',     
        'order_type', 
        'status', 'payment_method_on_closure', 'target_cash_register', 'created_at', 
        'get_total_order_amount_display' 
    )
    list_filter = (
        'status', 'order_type', 'created_at', 'manager', 'performer', 'client', 
        'payment_method_on_closure', 'target_cash_register'
    )
    search_fields = (
        'id', 'client__name', 'manager__username', 'manager__first_name', 
        'performer__username', 'performer__first_name', 'notes', 'order_type__name'
    )
    #autocomplete_fields = ['manager', 'performer', 'client', 'order_type']
    inlines = [OrderProductItemInline, OrderServiceItemInline]
    change_form_template = 'admin/orders/order/change_form_with_documents.html'

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

    def get_fieldsets(self, request, obj=None):
        main_fields_tuple = ('client', 'manager', 'performer', 'order_type', 'status', 'notes')
        if obj: 
            current_main_fields = list(main_fields_tuple)
            return (
                (None, {'fields': tuple(current_main_fields)}),
                ('Оплата и закрытие заказа', {'fields': ('payment_method_on_closure', 'target_cash_register')}),
                ('Суммы и даты (информация)', {'fields': ('get_total_order_amount_display', 'created_at', 'updated_at')}),
            )
        else: 
            new_order_main_fields = list(main_fields_tuple)
            if 'manager' in new_order_main_fields: # Менеджер будет назначен в save_model, на форме создания его можно скрыть
                 new_order_main_fields.remove('manager')
            return (
                (None, {'fields': tuple(new_order_main_fields)}), 
                ('Оплата и закрытие заказа', {'fields': ('payment_method_on_closure',)}),
                ('Суммы и даты (информация)', {'fields': ('get_total_order_amount_display',)}),
            )

    def get_readonly_fields(self, request, obj=None):
        base_readonly = ['created_at', 'updated_at', 'get_total_order_amount_display']
        
        can_edit_order_manager_group_name = "Редакторы ответственных в заказах" 
        user_can_edit_manager = request.user.is_superuser or \
                                request.user.groups.filter(name=can_edit_order_manager_group_name).exists()

        if obj: # Если это СУЩЕСТВУЮЩИЙ заказ (редактирование)
            if not user_can_edit_manager:
                base_readonly.append('manager')
            
            if obj.status == Order.STATUS_ISSUED:
                # Для выданных заказов делаем почти все поля readonly, включая order_type
                base_readonly.extend([
                    'status', 'payment_method_on_closure', 'client', 
                    'manager', 'performer', 'order_type'
                ])
            else:
                # Для НЕВЫДАННЫХ существующих заказов:
                # Поле 'order_type' делаем readonly, если у пользователя нет специального права
                # (суперюзеры по умолчанию имеют все права)
                if not request.user.has_perm('orders.can_change_order_type_dynamically'):
                    base_readonly.append('order_type')
        
        else: # Новый заказ (obj is None)
            # Для НОВЫХ заказов делаем order_type readonly, так как он определяется автоматически
            # или устанавливается в "Определить" и управляется JS (если мы это решим).
            # На данный момент JS не меняет тип на новой форме до первого сохранения.
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
            if 'manager' in form.base_fields: # Скрываем поле manager на форме создания
                form.base_fields['manager'].widget = admin.widgets.HiddenInput()
                form.base_fields['manager'].required = False 
        return form

    def _get_or_create_salary_calculation(self, request, order_instance, employee, role_context_key, role_verbose_name):
        salary_calc_obj, calc_created = SalaryCalculation.objects.get_or_create(
            employee=employee,
            order=order_instance,
            role_context=role_context_key,
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
        
        # Сообщение о создании/обновлении будет выведено после фактических начислений
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
        
        original_order_type_before_determination = order_instance.order_type
        if order_instance.determine_and_set_order_type(): 
            if order_instance.order_type != original_order_type_before_determination:
                order_instance.save(update_fields=['order_type', 'updated_at']) # Добавил updated_at
                messages.info(request, f"Тип заказа №{order_instance.id} автоматически определен/обновлен на '{order_instance.order_type}'.")

        previous_status_from_db = getattr(request, '_current_order_previous_status_from_db_for_save_related', None)
        current_status_in_object = order_instance.status
        
        is_newly_issued = (
            order_instance.pk is not None and
            current_status_in_object == Order.STATUS_ISSUED and
            previous_status_from_db != Order.STATUS_ISSUED
        )

        if is_newly_issued:
            print(f"[OrderAdmin SAVE_RELATED {order_instance.id}] Статус изменен на 'Выдан'. Предыдущий в БД: '{previous_status_from_db}'. Выполняем операции.")
            try:
                if not order_instance.payment_method_on_closure: 
                    raise ValidationError("Метод оплаты должен быть указан для статуса 'Выдан'.")
                
                determined_cash_register = None
                if order_instance.payment_method_on_closure == Order.ORDER_PAYMENT_METHOD_CASH:
                    try: determined_cash_register = CashRegister.objects.get(is_default_for_cash=True, is_active=True)
                    except CashRegister.DoesNotExist: raise ValidationError("Не найдена активная касса по умолчанию для НАЛИЧНЫХ.")
                    except CashRegister.MultipleObjectsReturned: raise ValidationError("Найдено несколько активных касс по умолчанию для НАЛИЧНЫХ.")
                elif order_instance.payment_method_on_closure == Order.ORDER_PAYMENT_METHOD_CARD:
                    try: determined_cash_register = CashRegister.objects.get(is_default_for_card=True, is_active=True)
                    except CashRegister.DoesNotExist: raise ValidationError("Не найдена активная касса по умолчанию для КАРТ.")
                    except CashRegister.MultipleObjectsReturned: raise ValidationError("Найдено несколько активных касс по умолчанию для КАРТ.")
                
                if not determined_cash_register:
                    raise ValidationError(f"Не удалось автоматически определить кассу для метода '{order_instance.get_payment_method_on_closure_display()}'.")

                current_order_total = order_instance.calculate_total_amount()
                if not (current_order_total > Decimal('0.00')):
                    raise ValidationError(f"Сумма заказа ({current_order_total}) должна быть > 0 для выдачи.")

                with transaction.atomic():
                    print(f"[OrderAdmin SAVE_RELATED {order_instance.id}] Внутри transaction.atomic() для статуса 'Выдан'.")
                    
                    for item_to_check_stock in order_instance.product_items.select_related('product').all():
                        # Используем Product.objects.select_for_update().get() для блокировки строки товара
                        product_obj_check = Product.objects.select_for_update().get(pk=item_to_check_stock.product.pk)
                        if product_obj_check.stock_quantity < item_to_check_stock.quantity:
                            raise ValidationError(f"Недостаточно товара '{product_obj_check.name}' на складе. Доступно: {product_obj_check.stock_quantity}, Требуется: {item_to_check_stock.quantity}.")
                    
                    for item_to_update_stock in order_instance.product_items.all():
                        # Повторно получаем объект для обновления, чтобы гарантировать актуальность, хотя select_for_update должен помочь
                        product_to_update = Product.objects.get(pk=item_to_update_stock.product.pk)
                        product_to_update.stock_quantity -= item_to_update_stock.quantity
                        product_to_update.save(update_fields=['stock_quantity'])
                    
                    order_instance.target_cash_register = determined_cash_register
                    order_instance.save(update_fields=['target_cash_register', 'updated_at']) # Обновляем и updated_at

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
                    
                    # --- БЛОК РАСЧЕТА ЗАРПЛАТЫ ---
                    earners_to_process = []
                    if order_instance.manager:
                        earners_to_process.append({
                            'employee_obj': order_instance.manager, 
                            'role_key_for_rate': EmployeeRate.ROLE_MANAGER,
                            'role_verbose': 'Менеджер',
                            'salary_calc_role_context': SalaryCalculation.ROLE_CONTEXT_MANAGER
                        })
                    
                    if order_instance.performer:
                        earners_to_process.append({
                            'employee_obj': order_instance.performer,
                            'role_key_for_rate': EmployeeRate.ROLE_PERFORMER,
                            'role_verbose': 'Исполнитель',
                            'salary_calc_role_context': SalaryCalculation.ROLE_CONTEXT_PERFORMER
                        })
                    
                    any_salary_calculated_this_session = False

                    for earner_info in earners_to_process:
                        employee = earner_info['employee_obj']
                        role_key_for_rate = earner_info['role_key_for_rate']
                        role_verbose_name = earner_info['role_verbose']
                        salary_calc_context_key = earner_info['salary_calc_role_context']

                        print(f"[Зарплата] Обработка для: {employee}, Роль: {role_verbose_name}, Тип заказа: {order_instance.order_type}")

                        employee_rate_instance = None
                        if order_instance.order_type: # Ставка зависит от типа заказа
                            try:
                                employee_rate_instance = EmployeeRate.objects.get(
                                    employee=employee,
                                    order_type=order_instance.order_type,
                                    role_in_order=role_key_for_rate,
                                    is_active=True
                                )
                                print(f"[Зарплата] Найдена ставка: {employee_rate_instance}")
                            except EmployeeRate.DoesNotExist:
                                print(f"[Зарплата] Ставка для {employee} (Роль: {role_verbose_name}, Тип заказа: {order_instance.order_type}) не найдена.")
                            except EmployeeRate.MultipleObjectsReturned:
                                print(f"[Зарплата] Найдено несколько активных ставок для {employee} (Роль: {role_verbose_name}, Тип заказа: {order_instance.order_type}). Используется первая.")
                                employee_rate_instance = EmployeeRate.objects.filter(
                                    employee=employee,
                                    order_type=order_instance.order_type,
                                    role_in_order=role_key_for_rate,
                                    is_active=True
                                ).first()
                        
                        if not employee_rate_instance:
                            messages.warning(request, f"Активная ставка для сотрудника {employee} (Роль: {role_verbose_name}) и типа заказа '{order_instance.order_type}' не найдена. Зарплата по этой роли/типу заказа не начислена.")
                            continue 

                        salary_calc_obj, sc_created, sc_preexisting_non_zero_calc = self._get_or_create_salary_calculation(
                            request, order_instance, employee, salary_calc_context_key, role_verbose_name
                        )
                        
                        # Удаляем старые детали для этого SalaryCalculation, чтобы избежать дублей при пересчете
                        # Это важно, если is_newly_issued может сработать не идеально или если логика меняется
                        if not sc_created: # Если расчет уже существовал, чистим его детали перед новым расчетом
                            print(f"[Зарплата] Очистка старых деталей для SalaryCalculation ID: {salary_calc_obj.id}")
                            salary_calc_obj.service_details.all().delete()
                            salary_calc_obj.product_profit_details.all().delete()
                            salary_calc_obj.total_calculated_amount = Decimal('0.00') # Сбрасываем сумму
                            # applied_base_rule_info и calculation_type будут перезаписаны ниже

                        current_session_earned_total_for_role = Decimal('0.00')
                        
                        # 1. Расчет от ПРИБЫЛИ ПО ТОВАРАМ
                        if employee_rate_instance.product_profit_percentage > Decimal('0.00'):
                            print(f"[Зарплата] Расчет от прибыли по товарам для {employee} ({role_verbose_name}), %: {employee_rate_instance.product_profit_percentage}")
                            for item in order_instance.product_items.all(): # Убедись, что cost_price_at_sale заполнено
                                if item.price_at_order is not None and item.cost_price_at_sale is not None and item.quantity > 0:
                                    profit_per_unit = item.price_at_order - item.cost_price_at_sale
                                    total_profit_for_line = profit_per_unit * item.quantity
                                    
                                    if total_profit_for_line > Decimal('0.00'):
                                        earned_from_profit = total_profit_for_line * (employee_rate_instance.product_profit_percentage / Decimal('100.00'))
                                        earned_from_profit = earned_from_profit.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                                        if earned_from_profit > Decimal('0.00'):
                                            ProductSalaryDetail.objects.create( # Создаем новую деталь без проверки на exists, т.к. старые удалили
                                                salary_calculation=salary_calc_obj,
                                                order_product_item=item,
                                                product_name_snapshot=item.product.name,
                                                product_price_at_sale=item.price_at_order,
                                                product_cost_at_sale=item.cost_price_at_sale,
                                                profit_from_item=total_profit_for_line.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                                                applied_percentage=employee_rate_instance.product_profit_percentage,
                                                earned_amount=earned_from_profit
                                            )
                                            current_session_earned_total_for_role += earned_from_profit
                                            print(f"[Зарплата] Начислено {earned_from_profit} от прибыли по '{item.product.name}' для {employee} ({role_verbose_name})")

                        # 2. Расчет от УСЛУГ
                        can_earn_from_services_for_this_role = True
                        if order_instance.order_type and order_instance.order_type.name == "Продажа":
                            # По твоей логике, в "Продаже" нет услуг для ЗП. 
                            # Но если менеджер все же может получать за услуги в продаже, уточни правило.
                            # Пока считаем, что в "Продаже" ЗП за услуги нет ни для кого.
                            can_earn_from_services_for_this_role = False 

                        if can_earn_from_services_for_this_role and employee_rate_instance.service_percentage > Decimal('0.00'):
                            print(f"[Зарплата] Расчет от услуг для {employee} ({role_verbose_name}), %: {employee_rate_instance.service_percentage}")
                            for service_item in order_instance.service_items.all():
                                base_amount = service_item.get_item_total()
                                if base_amount is not None and base_amount > Decimal('0.00'):
                                    earned_from_service = base_amount * (employee_rate_instance.service_percentage / Decimal('100.00'))
                                    earned_from_service = earned_from_service.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                                    if earned_from_service > Decimal('0.00'):
                                        SalaryCalculationDetail.objects.create( # Создаем новую деталь
                                            salary_calculation=salary_calc_obj,
                                            order_service_item=service_item,
                                            source_description=service_item.service.name,
                                            base_amount_for_calc=base_amount,
                                            applied_percentage=employee_rate_instance.service_percentage,
                                            earned_amount=earned_from_service,
                                            detail_type=f"service_{role_key_for_rate}"
                                        )
                                        current_session_earned_total_for_role += earned_from_service
                                        print(f"[Зарплата] Начислено {earned_from_service} от услуги '{service_item.service.name}' для {employee} ({role_verbose_name})")
                        
                        # Обновляем SalaryCalculation
                        if current_session_earned_total_for_role > Decimal('0.00') or sc_created: # Обновляем, если что-то начислено или это новый пустой расчет
                            salary_calc_obj.total_calculated_amount = current_session_earned_total_for_role.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                            
                            rule_parts = []
                            if employee_rate_instance.service_percentage > Decimal('0.00'):
                                rule_parts.append(f"Услуги: {employee_rate_instance.service_percentage}%")
                            if employee_rate_instance.product_profit_percentage > Decimal('0.00'):
                                rule_parts.append(f"Приб.тов.: {employee_rate_instance.product_profit_percentage}%")
                            
                            salary_calc_obj.applied_base_rule_info = (
                                f"Ставка для {role_verbose_name} ({employee.username}) "
                                f"в заказе типа '{order_instance.order_type.name if order_instance.order_type else 'N/A'}': "
                                f"{'; '.join(rule_parts) if rule_parts else 'Нет активных процентов для расчета'}."
                            )
                            salary_calc_obj.calculation_type = f"Сдельная ({role_verbose_name})"
                            salary_calc_obj.period_date = order_instance.updated_at.date() 
                            salary_calc_obj.save()
                            
                            any_salary_calculated_this_session = True
                            messages.success(request, f"Зарплата для {employee} (Роль: {role_verbose_name}) по заказу #{order_instance.id} начислена/обновлена: {salary_calc_obj.total_calculated_amount} руб.")
                        elif sc_preexisting_non_zero_calc: # Расчет был, но в эту сессию ничего не добавилось
                             messages.info(request, f"Для {employee} (Роль: {role_verbose_name}) по заказу #{order_instance.id} уже был произведен расчет ранее. Новых начислений в этой сессии нет.")

                    # Обновляем updated_at заказа в самом конце, если были какие-либо операции по зарплате
                    if any_salary_calculated_this_session:
                        order_instance.save(update_fields=['updated_at'])
            
            except ValidationError as e:
                order_instance.status = previous_status_from_db 
                order_instance.save(update_fields=['status'])
                if hasattr(e, 'message_dict'):
                    for field_name, error_list in e.message_dict.items():
                        for single_error_message in error_list:
                            field_label = field_name 
                            if field_name in form.fields:
                                field_label_from_form = form.fields.get(field_name)
                                if field_label_from_form and hasattr(field_label_from_form, 'label'):
                                    field_label = field_label_from_form.label
                            if field_label == '__all__':
                                messages.error(request, f"Ошибка: {single_error_message}")
                            else:
                                messages.error(request, f"Ошибка (поле: {field_label if field_label else 'Неизвестное поле'}): {single_error_message}")
                elif hasattr(e, 'messages') and isinstance(e.messages, list):
                    for single_error_message in e.messages:
                         messages.error(request, f"Ошибка: {single_error_message}")
                else:
                    messages.error(request, f"Ошибка при выдаче заказа №{order_instance.id}: {str(e)}")
        # else:
            # print(f"[OrderAdmin SAVE_RELATED {order_instance.id}] Заказ не является 'только что выданным'. Пропуск операций по выдаче и зарплате.")
            # pass


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
                messages.warning(request, "Не удалось определить тип контента для Заказа.")
            except Exception as e:
                extra_context['available_document_templates'] = None
                messages.error(request, f"Ошибка при получении шаблонов документов: {str(e)}")
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context,
        )
        
    class Media:
        js = (
            'admin/js/jquery.init.js',
            'orders/js/order_form_price_updater.js', 
            'orders/js/order_form_conditional_fields.js', 
        )
        css = { 
            'all': ('orders/css/admin_order_form.css',) 
        }