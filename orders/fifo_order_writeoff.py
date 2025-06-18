from .fifo_logic import calculate_and_assign_fifo_cost, calculate_virtual_fifo_cost, revert_fifo_write_off, reserve_fifo_stock, unreserve_fifo_stock

from decimal import Decimal

def handle_order_items_fifo_writeoff(order_instance):
    if not order_instance.pk:
        return

    if order_instance.status == order_instance.STATUS_ISSUED:
        # Заказ выдан — сначала снимаем резерв, потом списываем реально
        for item in order_instance.product_items.all():
            unreserve_fifo_stock(item)
            revert_fifo_write_off(item)           # если нужно вернуть списанное (при повторном сохранении)
            calculate_and_assign_fifo_cost(item)
            item.save(update_fields=['cost_price_at_sale'])
    else:
        # Любой другой статус — резервируем
        for item in order_instance.product_items.all():
            reserve_fifo_stock(item)
            calculate_virtual_fifo_cost(item)
            item.save(update_fields=['cost_price_at_sale'])