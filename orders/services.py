from suppliers.models import SupplyItem
from orders.models import OrderProductItem, Order

def recalculate_all_product_reserves():
    """
    Пересчитывает резервы для всех товаров по всем активным заказам.
    """
    # Сначала сбрасываем все резервы во всех партиях
    SupplyItem.objects.update(reserved_quantity=0)

    # Статусы, при которых заказ резервирует товар (замени на свои при необходимости!)
    ACTIVE_STATUSES = [
        Order.STATUS_NEW,
        Order.STATUS_IN_PROGRESS,
        Order.STATUS_AWAITING,
        Order.STATUS_READY,
        Order.STATUS_DELIVERING,
        Order.STATUS_NO_ANSWER,
    ]

    # Берём все строки товаров из активных заказов
    active_items = OrderProductItem.objects.filter(order__status__in=ACTIVE_STATUSES)

    # Для каждой строки заказа резервируем товар по FIFO
    for item in active_items:
        product = item.product
        qty_to_reserve = item.quantity
        left = qty_to_reserve

        batches = SupplyItem.objects.filter(
            product=product,
            quantity_remaining_in_batch__gt=0,
            supply__status='received'
        ).order_by('supply__receipt_date', 'pk')

        for batch in batches:
            free = batch.quantity_remaining_in_batch - batch.reserved_quantity
            to_reserve = min(left, free)
            if to_reserve > 0:
                batch.reserved_quantity += to_reserve
                batch.save(update_fields=['reserved_quantity'])
                left -= to_reserve
            if left <= 0:
                break