# orders/fifo_logic.py
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Sum, F
from django.core.exceptions import ValidationError

# Поскольку этот файл находится в 'orders', а SupplyItem в 'suppliers',
# используем полный путь импорта от корня проекта (предполагая, что 'erp' - это корень проекта,
# и он находится в PYTHONPATH, или Django сам разрешает такие импорты для приложений).
# Если 'erp' не является корневым пакетом в PYTHONPATH, возможно, понадобится 'suppliers.models'.
# Учитывая твою структуру F:\CRM 2.0\ERP\, 'suppliers' должно быть видно.
from suppliers.models import SupplyItem 
# Если будет ошибка импорта SupplyItem, попробуй:
# from erp.suppliers.models import SupplyItem 
# или настрой PYTHONPATH так, чтобы F:\CRM 2.0\ERP\ был в нем.

def calculate_and_assign_fifo_cost(order_item):
    """
    Рассчитывает себестоимость для OrderProductItem по методу FIFO,
    списывает остатки из партий SupplyItem и обновляет cost_price_at_sale.

    Args:
        order_item: Экземпляр OrderProductItem, у которого нужно установить cost_price_at_sale.
                    Предполагается, что order_item.product и order_item.quantity уже установлены.

    Raises:
        ValidationError: Если недостаточно товара на складе по партиям для продажи.
    """
    product_to_sell = order_item.product
    quantity_to_sell = order_item.quantity

    if not product_to_sell or quantity_to_sell is None or quantity_to_sell <= 0:
        order_item.cost_price_at_sale = Decimal('0.00')
        print(f"[FIFO Logic] Для позиции заказа ID {order_item.pk} (Товар: {product_to_sell}): "
              f"не указан товар или количество некорректно ({quantity_to_sell}). Себестоимость установлена в 0.")
        return

    # 1. Найти доступные партии этого товара, отсортированные по FIFO
    # (по дате прихода поставки, затем по ID самой позиции поставки для стабильности)
    # Используем select_for_update для блокировки строк на время транзакции (основная транзакция в OrderAdmin.save_related)
    available_batches = SupplyItem.objects.select_for_update().filter(
        product=product_to_sell,
        quantity_remaining_in_batch__gt=0
    ).order_by('supply__receipt_date', 'pk') # Сортируем по дате прихода связанной поставки

    # 2. Проверить общий доступный остаток по всем партиям
    total_quantity_in_batches = available_batches.aggregate(
        total_remaining=Sum('quantity_remaining_in_batch')
    )['total_remaining'] or Decimal('0.00') # Используем Decimal для согласованности

    print(f"[FIFO Logic] Для {product_to_sell.name} (продается {quantity_to_sell} шт.): "
          f"Общий остаток по партиям = {total_quantity_in_batches} шт.")

    if total_quantity_in_batches < quantity_to_sell:
        raise ValidationError(
            f"Недостаточно товара '{product_to_sell.name}' на складе по партиям для продажи {quantity_to_sell} шт. "
            f"Доступно по партиям: {total_quantity_in_batches}."
        )

    # 3. Списание из партий и расчет себестоимости
    cost_for_this_sale_total = Decimal('0.00')
    quantity_left_to_allocate = Decimal(str(quantity_to_sell)) # Работаем с Decimal для количества
    batches_used_info = [] 

    for batch in available_batches:
        if quantity_left_to_allocate <= Decimal('0.00'):
            break

        quantity_to_take_from_batch = min(quantity_left_to_allocate, Decimal(str(batch.quantity_remaining_in_batch)))
        
        cost_for_this_portion = quantity_to_take_from_batch * batch.cost_price_per_unit
        cost_for_this_sale_total += cost_for_this_portion
        
        # Обновляем остаток в партии
        batch.quantity_remaining_in_batch -= quantity_to_take_from_batch # quantity_remaining_in_batch это PositiveIntegerField, но операция вычитания с Decimal должна сработать
        batch.save(update_fields=['quantity_remaining_in_batch'])

        batches_used_info.append(
            f"Взято {quantity_to_take_from_batch} шт. из партии (SupplyItem ID: {batch.id}, остаток до: {batch.quantity_remaining_in_batch + quantity_to_take_from_batch}) "
            f"по себестоимости {batch.cost_price_per_unit}. Остаток в партии после: {batch.quantity_remaining_in_batch}"
        )
        
        quantity_left_to_allocate -= quantity_to_take_from_batch

    if quantity_left_to_allocate > Decimal('0.00'):
        # Эта ситуация не должна возникнуть, если предварительная проверка total_quantity_in_batches была верна
        # и все операции внутри цикла корректны.
        error_message = (f"Внутренняя ошибка при распределении остатков по партиям для товара '{product_to_sell.name}'. "
                         f"Не удалось распределить {quantity_left_to_allocate} шт.")
        print(f"[FIFO Logic] ОШИБКА: {error_message}")
        # Вместо ValidationError можно использовать более специфическое исключение или логировать серьезнее
        raise ValidationError(error_message) 

    # 4. Рассчитываем средневзвешенную себестоимость для этой конкретной продажи, если продается > 0
    if quantity_to_sell > 0:
        calculated_cost_at_sale = (cost_for_this_sale_total / Decimal(str(quantity_to_sell))).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        order_item.cost_price_at_sale = calculated_cost_at_sale
        print(f"[FIFO Logic] Для OrderItem ID {order_item.pk} ({product_to_sell.name}, {quantity_to_sell} шт.):")
        for info in batches_used_info:
            print(f"    - {info}")
        print(f"    Итоговая FIFO себестоимость для этой продажи (cost_price_at_sale): {calculated_cost_at_sale}")
    else: 
        order_item.cost_price_at_sale = Decimal('0.00')
        print(f"[FIFO Logic] Для OrderItem ID {order_item.pk}: количество к продаже 0, себестоимость установлена в 0.")

    # Сохранять order_item здесь не нужно, это сделает вызывающий код (OrderAdmin.save_related)
    # после того, как все order_item в заказе будут обработаны и их cost_price_at_sale установлена.