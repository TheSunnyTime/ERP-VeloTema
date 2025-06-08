# orders/deadlines/services.py
from django.utils import timezone
from datetime import timedelta
from ..models import Order, OrderType, ServiceCategory # Убедимся, что OrderType импортирован

# --- Константы ---
REPAIR_ORDER_TYPE_NAME = OrderType.TYPE_REPAIR 
COMPLEX_SERVICE_CATEGORY_NAME = "Комплексное обслуживание"
BASE_DAYS_FOR_REPAIR_ORDER = 2
DAYS_SHIFT_FOR_COMPLEX_LOAD = 1
N_OVERALL_COMPLEX_ORDERS_FOR_SHIFT = 2
DEFAULT_FALLBACK_DUE_DAYS = 3 
# --- Конец констант ---

_complex_category_id_cache = None

def get_complex_service_category_id():
    global _complex_category_id_cache 
    if _complex_category_id_cache is None:
        try:
            category = ServiceCategory.objects.get(name=COMPLEX_SERVICE_CATEGORY_NAME)
            _complex_category_id_cache = category.id
            print(f"[Deadlines SVC] Кэширован ID для '{COMPLEX_SERVICE_CATEGORY_NAME}': {_complex_category_id_cache}")
        except ServiceCategory.DoesNotExist:
            print(f"[Deadlines SVC] ВНИМАНИЕ: Категория услуг '{COMPLEX_SERVICE_CATEGORY_NAME}' не найдена в БД!")
            _complex_category_id_cache = -1 
    return _complex_category_id_cache if _complex_category_id_cache != -1 else None

def is_order_complex(order_instance):
    if not order_instance: return False
    complex_category_id = get_complex_service_category_id()
    if complex_category_id is None: return False
    
    if hasattr(order_instance, '_prefetched_objects_cache') and 'service_items' in order_instance._prefetched_objects_cache:
        return any(item.service.category_id == complex_category_id for item in order_instance.service_items.all())
    elif order_instance.pk:
        return order_instance.service_items.filter(service__category_id=complex_category_id).exists()
    else:
        print(f"[Deadlines SVC is_order_complex] Заказ новый (нет PK), проверка комплексности может быть неточной.")
        return False

def _calculate_due_date_for_simple_repair(base_date=None):
    current_date = base_date or timezone.now().date()
    if hasattr(current_date, 'date'): current_date = current_date.date()
    return current_date + timedelta(days=BASE_DAYS_FOR_REPAIR_ORDER)

def _calculate_due_date_for_complex_repair(order_instance, base_date=None):
    print(f"[Deadlines SVC _calc_complex_repair] для заказа ID: {order_instance.id if order_instance.pk else 'Новый'}")
    current_date = base_date or timezone.now().date()
    if hasattr(current_date, 'date'): current_date = current_date.date()
    days_shift = 0
    complex_category_id = get_complex_service_category_id()
    if complex_category_id is not None:
        active_repair_orders_qs = Order.objects.filter(
            order_type__name=REPAIR_ORDER_TYPE_NAME,
            status__in=[Order.STATUS_IN_PROGRESS, Order.STATUS_AWAITING, Order.STATUS_NEW],
            service_items__service__category_id=complex_category_id
        ).distinct()
        if order_instance.pk:
            active_repair_orders_qs = active_repair_orders_qs.exclude(pk=order_instance.pk)
        count_overall_active_complex_orders = active_repair_orders_qs.count()
        if N_OVERALL_COMPLEX_ORDERS_FOR_SHIFT > 0:
            days_shift = (count_overall_active_complex_orders // N_OVERALL_COMPLEX_ORDERS_FOR_SHIFT) * DAYS_SHIFT_FOR_COMPLEX_LOAD
        print(f"[Deadlines SVC _calc_complex_repair] Общая загрузка: {count_overall_active_complex_orders} компл. заказов. Сдвиг: {days_shift} дней.")
    else:
        print(f"[Deadlines SVC _calc_complex_repair] Категория '{COMPLEX_SERVICE_CATEGORY_NAME}' не найдена. Сдвиг = 0.")
    calculated_due_date = current_date + timedelta(days=BASE_DAYS_FOR_REPAIR_ORDER + days_shift)
    min_possible_due_date = current_date + timedelta(days=BASE_DAYS_FOR_REPAIR_ORDER)
    final_due_date = max(calculated_due_date, min_possible_due_date)
    print(f"[Deadlines SVC _calc_complex_repair] Итоговый срок: {final_due_date}")
    return final_due_date

def _calculate_fallback_due_date(order_instance):
    base_date_for_fallback = order_instance.created_at if order_instance.created_at else timezone.now()
    if hasattr(base_date_for_fallback, 'date'): base_date_for_fallback = base_date_for_fallback.date()
    return base_date_for_fallback + timedelta(days=DEFAULT_FALLBACK_DUE_DAYS)

def determine_and_update_order_due_date(order_instance, is_new_order, was_complex_before_save, original_order_type_name_before_determination):
    print(f"[Deadlines SVC determine_and_update] Заказ ID: {order_instance.id if order_instance.pk else 'Новый'}. "
          f"Новый: {is_new_order}, Был комплексным: {was_complex_before_save}, "
          f"Тип до: '{original_order_type_name_before_determination}', Тип сейчас: '{order_instance.order_type.name if order_instance.order_type else 'N/A'}'")

    current_order_type_name = order_instance.order_type.name if order_instance.order_type else None

    # --- НАЧАЛО ИЗМЕНЕНИЙ ---
    if current_order_type_name == OrderType.TYPE_UNDEFINED:
        print(f"[Deadlines SVC determine_and_update] Тип '{OrderType.TYPE_UNDEFINED}'. Срок принудительно None.")
        return None 

    if current_order_type_name == OrderType.TYPE_SALE:
        print(f"[Deadlines SVC determine_and_update] Тип '{OrderType.TYPE_SALE}'. Срок управляется вручную. Возвращаем значение из инстанса: {order_instance.due_date}.")
        # Для "Продажи" срок берется из формы (уже в order_instance.due_date, если поле было редактируемым).
        # Если тип только что изменился на "Продажа", и поле было readonly, order_instance.due_date содержит старое значение.
        # Если это новый заказ "Продажа", order_instance.due_date будет None (если не установлено в форме по умолчанию).
        return order_instance.due_date # Возвращаем текущее значение на инстансе (из формы или сохраненное)
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    if current_order_type_name == REPAIR_ORDER_TYPE_NAME:
        is_complex_now = is_order_complex(order_instance)
        print(f"[Deadlines SVC determine_and_update] Заказ '{REPAIR_ORDER_TYPE_NAME}'. Стал комплексным сейчас: {is_complex_now}")
        
        base_calculation_date = order_instance.created_at if is_new_order else timezone.now()

        if is_new_order:
            if is_complex_now:
                new_due_date = _calculate_due_date_for_complex_repair(order_instance, base_date=base_calculation_date)
                print(f"[Deadlines SVC determine_and_update] Новый '{REPAIR_ORDER_TYPE_NAME}', комплексный. Срок: {new_due_date}")
                return new_due_date
            else:
                new_due_date = _calculate_due_date_for_simple_repair(base_date=base_calculation_date)
                print(f"[Deadlines SVC determine_and_update] Новый '{REPAIR_ORDER_TYPE_NAME}', простой. Срок: {new_due_date}")
                return new_due_date
        else: # Существующий заказ типа "Ремонт"
            type_just_changed_to_repair = (original_order_type_name_before_determination != REPAIR_ORDER_TYPE_NAME and
                                           current_order_type_name == REPAIR_ORDER_TYPE_NAME)

            if not was_complex_before_save and is_complex_now:
                new_due_date = _calculate_due_date_for_complex_repair(order_instance, base_date=base_calculation_date)
                print(f"[Deadlines SVC determine_and_update] Существующий '{REPAIR_ORDER_TYPE_NAME}'. Стал комплексным. Новый срок: {new_due_date}")
                return new_due_date
            elif was_complex_before_save and not is_complex_now:
                new_due_date = _calculate_due_date_for_simple_repair(base_date=base_calculation_date)
                print(f"[Deadlines SVC determine_and_update] Существующий '{REPAIR_ORDER_TYPE_NAME}'. Перестал быть комплексным. Новый срок: {new_due_date}")
                return new_due_date
            elif was_complex_before_save and is_complex_now:
                print(f"[Deadlines SVC determine_and_update] Существующий '{REPAIR_ORDER_TYPE_NAME}'. Был и остался комплексным. Срок НЕ меняется.")
                return None
            elif not was_complex_before_save and not is_complex_now:
                if type_just_changed_to_repair:
                    new_due_date = _calculate_due_date_for_simple_repair(base_date=base_calculation_date)
                    print(f"[Deadlines SVC determine_and_update] Существующий. Тип только что стал '{REPAIR_ORDER_TYPE_NAME}' (простой). Новый срок: {new_due_date}")
                    return new_due_date
                print(f"[Deadlines SVC determine_and_update] Существующий '{REPAIR_ORDER_TYPE_NAME}'. Был и остался простым. Срок НЕ меняется.")
                return None
        return None # На всякий случай, если какая-то ветка для "Ремонта" не вернула значение

    # Fallback для других типов (если такие появятся) или если тип None
    # Эта логика сработает, если current_order_type_name не "Ремонт", не "Продажа", не "Определить".
    if is_new_order or (original_order_type_name_before_determination != current_order_type_name):
        new_due_date = _calculate_fallback_due_date(order_instance)
        print(f"[Deadlines SVC determine_and_update] Тип '{current_order_type_name}' (неизвестный/прочее) или изменился. Расчет fallback: {new_due_date}")
        return new_due_date
        
    return None # По умолчанию не меняем срок