# F:\CRM 2.0\erp\orders\admin\order_admin.py
from django.contrib import admin, messages
from django.contrib.auth.models import User, Group # Используется в get_readonly_fields
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F # <--- ДОБАВЛЕН ИМПОРТ F
from decimal import Decimal, ROUND_HALF_UP
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse 
from django.utils import timezone 
from django.utils.html import format_html
from uiconfig.models import OrderStatusColor # Наше приложение с цветами

# Импорты из текущего приложения orders
from ..models import Order, OrderType # Product здесь не нужен, он импортируется ниже из products.models
from ..forms import OrderAdminForm # Убедись, что BaseOrderProductItemFormSet удален или импортируется, если нужен в OrderAdminForm
from ..fifo_logic import calculate_and_assign_fifo_cost 

# Импортируем инлайны из соседнего файла в этом же пакете admin
from .order_inlines_admin import OrderProductItemInline, OrderServiceItemInline

# Импорты моделей из других приложений
from salary_management.models import EmployeeRate, SalaryCalculation, SalaryCalculationDetail, ProductSalaryDetail
from utils.models import DocumentTemplate
from products.models import Product # Импорт Product
from cash_register.models import CashRegister, CashTransaction


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    form = OrderAdminForm
    list_display = (
        'id', 
        'client', 
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
    )
    search_fields = ( # Убедись, что это поле не пустое
        'id', 'client__name', 'manager__username', 'manager__first_name', 
        'performer__username', 'performer__first_name', 'notes', 'order_type__name'
    )
    autocomplete_fields = ['manager', 'performer', 'client',] # Раскомментировал, если они нужны
    inlines = [OrderProductItemInline, OrderServiceItemInline]
    change_form_template = 'admin/orders/order/change_form_with_documents.html'


    def __init__(self, model, admin_site): # <--- ДОБАВЛЕН КОНСТРУКТОР
        super().__init__(model, admin_site)
        # Загружаем все настроенные цвета статусов один раз
        # чтобы не делать запрос к БД для каждой строки списка
        self.status_colors_map = {
            color_setting.status_key: color_setting.hex_color
            for color_setting in OrderStatusColor.objects.all()
        }

    # --- Методы для отображения в list_display ---
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
    
    def colored_status(self, obj): # <--- НАШ НОВЫЙ МЕТОД
        status_key = obj.status
        display_name = obj.get_status_display() # Человекочитаемое имя статуса
        hex_color = self.status_colors_map.get(status_key, '#FFFFFF') # Белый по умолчанию, если цвет не найден

        # Простая логика для определения цвета текста для лучшего контраста
        # Это очень упрощенный вариант. Для более точного определения нужен анализ яркости.
        try:
            r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            text_color = '#000000' if luminance > 0.5 else '#FFFFFF'
        except: # На случай некорректного HEX или если нет #
            text_color = '#000000'


        return format_html(
            '<span style="background-color: {}; color: {}; padding: 5px 10px; border-radius: 4px;">{}</span>',
            hex_color,
            text_color, # Используем рассчитанный цвет текста
            display_name,
        )
    colored_status.short_description = "Статус" # Название колонки
    colored_status.admin_order_field = 'status' # Позволяет сортировку по оригинальному полю статуса

    # --- Конфигурация полей и формы ---
    def get_fieldsets(self, request, obj=None):
        main_fields_tuple = ('client', 'manager', 'performer', 'order_type', 'repaired_item', 'status', 'notes')
        
        payment_closure_fieldset_fields = ['payment_method_on_closure'] # Базовое поле для этого fieldset

        # Проверяем, есть ли у пользователя право видеть 'target_cash_register'
        if request.user.is_superuser or request.user.has_perm('orders.can_view_target_cash_register'):
            payment_closure_fieldset_fields.append('target_cash_register')

        if obj:  # Для существующего заказа
            current_main_fields = list(main_fields_tuple)
            # Если нужно, здесь можно добавить/удалить 'manager' или 'performer' из current_main_fields
            # в зависимости от того, редактируется заказ или просматривается, и какие права у юзера.
            # Твоя текущая логика для 'manager' на странице создания остается ниже.

            fieldsets_config = (
                (None, {'fields': tuple(current_main_fields)}),
                ('Оплата и закрытие заказа', {
                    'fields': tuple(payment_closure_fieldset_fields) # Используем сформированный список полей
                }),
                ('Суммы и даты (информация)', {
                    'fields': ('get_total_order_amount_display', 'created_at', 'updated_at')
                }),
            )
            return fieldsets_config
        else:  # Для нового заказа
            new_order_main_fields = list(main_fields_tuple)
            if 'manager' in new_order_main_fields: # Скрываем 'manager' при создании, он назначается автоматически
                new_order_main_fields.remove('manager')
            
            # Для нового заказа поле target_cash_register обычно не показывается сразу,
            # так как оно определяется автоматически при переводе в статус "Выдан".
            # Если ты хочешь его показывать и для новых заказов (при наличии прав),
            # то нужно будет аналогично добавить его в payment_closure_fieldset_fields_new.
            # Пока оставляем как было в твоей логике (target_cash_register не было для новых).
            payment_closure_fieldset_fields_new = ['payment_method_on_closure']
            # Если нужно и для новых (и есть права):
            # if request.user.is_superuser or request.user.has_perm('orders.can_view_target_cash_register'):
            # payment_closure_fieldset_fields_new.append('target_cash_register')


            fieldsets_config_new = (
                (None, {'fields': tuple(new_order_main_fields)}),
                ('Оплата и закрытие заказа', {
                    'fields': tuple(payment_closure_fieldset_fields_new) 
                }),
                ('Суммы и даты (информация)', {
                    'fields': ('get_total_order_amount_display',) # 'created_at', 'updated_at' для новых не нужны
                }),
            )
            return fieldsets_config_new

    def get_readonly_fields(self, request, obj=None):
        base_readonly = ['created_at', 'updated_at', 'get_total_order_amount_display']
        can_edit_order_manager_group_name = "Редакторы ответственных в заказах" 
        user_can_edit_manager = request.user.is_superuser or \
                                request.user.groups.filter(name=can_edit_order_manager_group_name).exists()
        if obj: 
            if not user_can_edit_manager:
                base_readonly.append('manager')
            
            current_status_in_db = obj.status
            # db_obj_order_type = obj.order_type # Не используем здесь, чтобы не влиять на рендеринг select
            
            if current_status_in_db == Order.STATUS_ISSUED:
                base_readonly.extend(['status', 'payment_method_on_closure', 'client', 
                                      'manager', 'performer', 'order_type'])
            else: # Для невыданных заказов
                if not request.user.has_perm('orders.can_change_order_type_dynamically'):
                    base_readonly.append('order_type') # Делаем readonly, если нет прав
        else: # Новый заказ
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

    # --- Логика сохранения и расчета зарплат ---
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
                order_instance.updated_at = timezone.now()
                order_instance.save(update_fields=['order_type', 'updated_at'])
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
                    
                    # 1. Обрабатываем FIFO и обновляем cost_price_at_sale для каждой товарной позиции
                    for order_item_instance in order_instance.product_items.all():
                        print(f"[OrderAdmin SAVE_RELATED] Обработка FIFO для: {order_item_instance}")
                        try:
                            calculate_and_assign_fifo_cost(order_item_instance) 
                            order_item_instance.save(update_fields=['cost_price_at_sale']) 
                            print(f"[OrderAdmin SAVE_RELATED] Сохранена cost_price_at_sale ({order_item_instance.cost_price_at_sale}) для {order_item_instance}")
                        except ValidationError as e_fifo:
                            messages.error(request, f"Ошибка FIFO для товара '{order_item_instance.product.name}': {str(e_fifo)}") 
                            raise # Перевыбрасываем ошибку, чтобы откатить транзакцию
                    
                    # 2. Обновляем ОБЩИЕ остатки Product.stock_quantity
                    for item_to_update_stock in order_instance.product_items.all():
                        product_to_update = Product.objects.select_for_update().get(pk=item_to_update_stock.product.pk)
                        if product_to_update.stock_quantity < item_to_update_stock.quantity:
                             # Эта проверка дублируется с той, что внутри calculate_and_assign_fifo_cost, 
                             # но здесь она проверяет общий остаток, а FIFO - остаток по партиям.
                             # Если FIFO прошел, эта проверка тоже должна пройти.
                            raise ValidationError(f"Недостаточно общего остатка товара '{product_to_update.name}' на складе. Доступно: {product_to_update.stock_quantity}, Требуется: {item_to_update_stock.quantity}.")
                        
                        product_to_update.stock_quantity = F('stock_quantity') - item_to_update_stock.quantity
                        update_fields_for_product = ['stock_quantity']
                        if hasattr(product_to_update, 'updated_at'): # Если у Product есть updated_at
                            update_fields_for_product.append('updated_at')
                        product_to_update.save(update_fields=update_fields_for_product)
                        print(f"[OrderAdmin SAVE_RELATED] Обновлен общий остаток для {product_to_update.name}: -{item_to_update_stock.quantity}")
                    
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
                        if order_instance.order_type:
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
                                print(f"[Зарплата] Найдено несколько активных ставок. Используется первая.")
                                employee_rate_instance = EmployeeRate.objects.filter(
                                    employee=employee, order_type=order_instance.order_type,
                                    role_in_order=role_key_for_rate, is_active=True
                                ).first()
                        
                        if not employee_rate_instance:
                            messages.warning(request, f"Активная ставка для {employee} ({role_verbose_name}) для типа заказа '{order_instance.order_type}' не найдена. ЗП не начислена.")
                            continue 

                        salary_calc_obj, sc_created, sc_preexisting_non_zero_calc = self._get_or_create_salary_calculation(
                            request, order_instance, employee, salary_calc_context_key, role_verbose_name
                        )
                        
                        if not sc_created: 
                            print(f"[Зарплата] Очистка старых деталей для SalaryCalculation ID: {salary_calc_obj.id}")
                            salary_calc_obj.service_details.all().delete()
                            salary_calc_obj.product_profit_details.all().delete()
                            salary_calc_obj.total_calculated_amount = Decimal('0.00') 
                        
                        current_session_earned_total_for_role = Decimal('0.00')
                        
                        if employee_rate_instance.product_profit_percentage > Decimal('0.00'):
                            print(f"[Зарплата] Расчет от прибыли товаров для {employee} ({role_verbose_name}), %: {employee_rate_instance.product_profit_percentage}")
                            for item in order_instance.product_items.all(): 
                                if item.price_at_order is not None and item.cost_price_at_sale is not None and item.quantity > 0:
                                    profit_per_unit = item.price_at_order - item.cost_price_at_sale 
                                    total_profit_for_line = profit_per_unit * item.quantity
                                    if total_profit_for_line > Decimal('0.00'):
                                        earned_from_profit = total_profit_for_line * (employee_rate_instance.product_profit_percentage / Decimal('100.00'))
                                        earned_from_profit = earned_from_profit.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                                        if earned_from_profit > Decimal('0.00'):
                                            ProductSalaryDetail.objects.create(
                                                salary_calculation=salary_calc_obj, order_product_item=item,
                                                product_name_snapshot=item.product.name, product_price_at_sale=item.price_at_order,
                                                product_cost_at_sale=item.cost_price_at_sale, 
                                                profit_from_item=total_profit_for_line.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                                                applied_percentage=employee_rate_instance.product_profit_percentage,
                                                earned_amount=earned_from_profit
                                            )
                                            current_session_earned_total_for_role += earned_from_profit
                                            print(f"[Зарплата] +{earned_from_profit} (прибыль) по '{item.product.name}' для {employee} ({role_verbose_name})")

                        can_earn_from_services = order_instance.order_type and order_instance.order_type.name != "Продажа"
                        if can_earn_from_services and employee_rate_instance.service_percentage > Decimal('0.00'):
                            print(f"[Зарплата] Расчет от услуг для {employee} ({role_verbose_name}), %: {employee_rate_instance.service_percentage}")
                            for service_item in order_instance.service_items.all():
                                base_amount = service_item.get_item_total()
                                if base_amount is not None and base_amount > Decimal('0.00'):
                                    earned_from_service = base_amount * (employee_rate_instance.service_percentage / Decimal('100.00'))
                                    earned_from_service = earned_from_service.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                                    if earned_from_service > Decimal('0.00'):
                                        SalaryCalculationDetail.objects.create(
                                            salary_calculation=salary_calc_obj, order_service_item=service_item,
                                            source_description=service_item.service.name, base_amount_for_calc=base_amount,
                                            applied_percentage=employee_rate_instance.service_percentage,
                                            earned_amount=earned_from_service, detail_type=f"service_{role_key_for_rate}"
                                        )
                                        current_session_earned_total_for_role += earned_from_service
                                        print(f"[Зарплата] +{earned_from_service} (услуга) по '{service_item.service.name}' для {employee} ({role_verbose_name})")
                        
                        if current_session_earned_total_for_role > Decimal('0.00') or sc_created or (not sc_created and sc_preexisting_non_zero_calc and salary_calc_obj.total_calculated_amount != current_session_earned_total_for_role):
                            salary_calc_obj.total_calculated_amount = current_session_earned_total_for_role.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                            rule_parts = []
                            if salary_calc_obj.service_details.filter(earned_amount__gt=0).exists(): # Проверяем, были ли РЕАЛЬНЫЕ начисления по услугам
                                rule_parts.append(f"Услуги: {employee_rate_instance.service_percentage}%")
                            if salary_calc_obj.product_profit_details.filter(earned_amount__gt=0).exists(): # Проверяем, были ли РЕАЛЬНЫЕ начисления по прибыли
                                rule_parts.append(f"Приб.тов.: {employee_rate_instance.product_profit_percentage}%")
                            
                            salary_calc_obj.applied_base_rule_info = (
                                f"Ставка для {role_verbose_name} ({employee.username}) "
                                f"в заказе типа '{order_instance.order_type.name if order_instance.order_type else 'N/A'}': "
                                f"{'; '.join(rule_parts) if rule_parts else 'Ставка применена, начислений нет'}."
                            )
                            salary_calc_obj.calculation_type = f"Сдельная ({role_verbose_name})"
                            salary_calc_obj.period_date = order_instance.updated_at.date() 
                            salary_calc_obj.save()
                            any_salary_calculated_this_session = True
                            messages.success(request, f"Зарплата для {employee} (Роль: {role_verbose_name}) по заказу #{order_instance.id} начислена/обновлена: {salary_calc_obj.total_calculated_amount} руб.")
                        elif not sc_created and not sc_preexisting_non_zero_calc and current_session_earned_total_for_role == Decimal('0.00'):
                             messages.info(request, f"Для {employee} (Роль: {role_verbose_name}) по заказу #{order_instance.id} в этой сессии начислений не произведено.")

                    if any_salary_calculated_this_session:
                        order_instance.updated_at = timezone.now()
                        order_instance.save(update_fields=['updated_at'])
            
            except ValidationError as e:
                # ... (твой существующий блок обработки ValidationError) ...
                order_instance.status = previous_status_from_db 
                order_instance.updated_at = timezone.now() 
                order_instance.save(update_fields=['status', 'updated_at'])
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

    def change_view(self, request, object_id, form_url='', extra_context=None):
        # ... (твой существующий change_view) ...
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
            'admin/js/jquery.init.js', # Важно для django.jQuery
            'orders/js/order_form_price_updater.js', 
            'orders/js/order_form_conditional_fields.js', 
        )
        css = { 
            'all': ('orders/css/admin_order_form.css',) # Если есть кастомные стили
        }