# orders/deadlines/services.py
from django.utils import timezone
from datetime import timedelta
# Нужны импорты моделей
from ..models import Order, OrderType, ServiceCategory # ServiceCategory теперь тоже нужна

# --- Константы для расчета срока ---
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
            print(f"[Deadlines SVC] ВНИМАНИЕ: Категория услуг '{COMPLEX_SERVICE_CATEGORY_NAME}' не найдена в БД! Расчет сдвига по комплексным услугам не будет работать корректно.")
            _complex_category_id_cache = -1 
    
    return _complex_category_id_cache if _complex_category_id_cache != -1 else None


def calculate_due_date_based_on_overall_load(order_instance):
    print(f"[Deadlines SVC] ==> calculate_due_date_based_on_overall_load для заказа ID: {order_instance.id if order_instance.pk else 'Новый (нет PK)'}")

    complex_category_id = get_complex_service_category_id()
    days_shift = 0 

    if complex_category_id is not None:
        print(f"[Deadlines SVC] ID комплексной категории: {complex_category_id}")
        active_repair_orders_with_complex_service_qs = Order.objects.filter(
            order_type__name=REPAIR_ORDER_TYPE_NAME, 
            status__in=[
                Order.STATUS_IN_PROGRESS, 
                Order.STATUS_AWAITING,
                Order.STATUS_NEW # <--- ДОБАВЛЕН СТАТУС "НОВЫЙ"
            ], 
            service_items__service__category_id=complex_category_id
        )

        if order_instance.pk:
            print(f"[Deadlines SVC] Исключаем текущий редактируемый заказ (ID: {order_instance.pk}) из подсчета загрузки.")
            active_repair_orders_with_complex_service_qs = active_repair_orders_with_complex_service_qs.exclude(pk=order_instance.pk)
        
        count_overall_active_complex_orders = active_repair_orders_with_complex_service_qs.distinct().count()
        print(f"[Deadlines SVC] Найдено активных комплексных ремонтных заказов (кроме текущего, если он редактируется): {count_overall_active_complex_orders}")

        if N_OVERALL_COMPLEX_ORDERS_FOR_SHIFT > 0: 
            days_shift = (count_overall_active_complex_orders // N_OVERALL_COMPLEX_ORDERS_FOR_SHIFT) * DAYS_SHIFT_FOR_COMPLEX_LOAD
        print(f"[Deadlines SVC] Рассчитанный сдвиг дней из-за общей загрузки: {days_shift}")
    else:
        print(f"[Deadlines SVC] Категория '{COMPLEX_SERVICE_CATEGORY_NAME}' не найдена или ошибка при получении ID. Сдвиг дней не рассчитывается (days_shift = 0).")
    
    current_date = timezone.now().date()
    calculated_due_date = current_date + timedelta(days=BASE_DAYS_FOR_REPAIR_ORDER + days_shift)
    min_possible_due_date = current_date + timedelta(days=BASE_DAYS_FOR_REPAIR_ORDER)
    final_due_date = max(calculated_due_date, min_possible_due_date)
    
    print(f"[Deadlines SVC] Базовый срок: {BASE_DAYS_FOR_REPAIR_ORDER} дней. Итоговый срок выполнения: {final_due_date}")
    return final_due_date


def calculate_initial_due_date(order_instance):
    print(f"[Deadlines SVC] ==> calculate_initial_due_date для заказа ID: {order_instance.id if order_instance.pk else 'Новый (нет PK)'}")
    order_type_name_for_logic = order_instance.order_type.name if order_instance.order_type else "ТИП НЕ УСТАНОВЛЕН"
    print(f"[Deadlines SVC] Тип заказа, полученный в calculate_initial_due_date: '{order_type_name_for_logic}'")
    
    if order_instance.order_type and order_instance.order_type.name == REPAIR_ORDER_TYPE_NAME:
        print(f"[Deadlines SVC] Заказ типа '{REPAIR_ORDER_TYPE_NAME}', применяем расчет на основе загрузки.")
        return calculate_due_date_based_on_overall_load(order_instance)
    else:
        print(f"[Deadlines SVC] Заказ типа '{order_type_name_for_logic}', применяем стандартный расчет срока (+{DEFAULT_FALLBACK_DUE_DAYS} дня).")
        
        base_date_for_fallback = order_instance.created_at if order_instance.created_at else timezone.now()
        # Убедимся, что base_date_for_fallback это объект date, если это datetime
        if hasattr(base_date_for_fallback, 'date'):
            base_date_for_fallback = base_date_for_fallback.date()
            
        final_fallback_due_date = base_date_for_fallback + timedelta(days=DEFAULT_FALLBACK_DUE_DAYS)
        print(f"[Deadlines SVC] Стандартный срок выполнения: {final_fallback_due_date}")
        return final_fallback_due_date