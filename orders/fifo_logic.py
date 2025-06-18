from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Sum, F
from django.core.exceptions import ValidationError
from suppliers.models import SupplyItem

def calculate_virtual_fifo_cost(order_item):
    """
    Виртуально считает себестоимость по FIFO, НЕ изменяя остатки партий.
    Использовать для резервирования (статусы кроме "Выдан").
    """
    product_to_sell = order_item.product
    quantity_to_sell = order_item.quantity

    if not product_to_sell or quantity_to_sell is None or quantity_to_sell <= 0:
        order_item.cost_price_at_sale = Decimal('0.00')
        return

    available_batches = SupplyItem.objects.filter(
        product=product_to_sell,
        quantity_remaining_in_batch__gt=0
    ).order_by('supply__receipt_date', 'pk')

    total_quantity_in_batches = available_batches.aggregate(
        total_remaining=Sum('quantity_remaining_in_batch')
    )['total_remaining'] or Decimal('0.00')

    if total_quantity_in_batches < quantity_to_sell:
        raise ValidationError(
            f"Недостаточно товара '{product_to_sell.name}' на складе для бронирования {quantity_to_sell} шт. "
            f"Доступно: {total_quantity_in_batches}."
        )

    cost_for_this_sale_total = Decimal('0.00')
    quantity_left = Decimal(str(quantity_to_sell))
    for batch in available_batches:
        if quantity_left <= 0:
            break
        qty = min(quantity_left, Decimal(str(batch.quantity_remaining_in_batch)))
        cost_for_this_sale_total += qty * batch.cost_price_per_unit
        quantity_left -= qty

    if quantity_left > 0:
        raise ValidationError(
            f"(Виртуально) Не удалось распределить {quantity_left} шт. по партиям для товара '{product_to_sell.name}'."
        )

    if quantity_to_sell > 0:
        calculated_cost = (cost_for_this_sale_total / Decimal(str(quantity_to_sell))).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        order_item.cost_price_at_sale = calculated_cost
    else:
        order_item.cost_price_at_sale = Decimal('0.00')

def calculate_and_assign_fifo_cost(order_item):
    """
    Реально списывает товар из партий и считает себестоимость (использовать только при статусе "Выдан").
    """
    product_to_sell = order_item.product
    quantity_to_sell = order_item.quantity

    if not product_to_sell or quantity_to_sell is None or quantity_to_sell <= 0:
        order_item.cost_price_at_sale = Decimal('0.00')
        return

    available_batches = SupplyItem.objects.select_for_update().filter(
        product=product_to_sell,
        quantity_remaining_in_batch__gt=0
    ).order_by('supply__receipt_date', 'pk')

    total_quantity_in_batches = available_batches.aggregate(
        total_remaining=Sum('quantity_remaining_in_batch')
    )['total_remaining'] or Decimal('0.00')

    if total_quantity_in_batches < quantity_to_sell:
        raise ValidationError(
            f"Недостаточно товара '{product_to_sell.name}' на складе для продажи {quantity_to_sell} шт. "
            f"Доступно: {total_quantity_in_batches}."
        )

    cost_for_this_sale_total = Decimal('0.00')
    quantity_left_to_allocate = Decimal(str(quantity_to_sell))

    for batch in available_batches:
        if quantity_left_to_allocate <= 0:
            break
        quantity_to_take_from_batch = min(quantity_left_to_allocate, Decimal(str(batch.quantity_remaining_in_batch)))
        cost_for_this_portion = quantity_to_take_from_batch * batch.cost_price_per_unit
        cost_for_this_sale_total += cost_for_this_portion

        # Реально списываем
        batch.quantity_remaining_in_batch -= quantity_to_take_from_batch
        batch.save(update_fields=['quantity_remaining_in_batch'])

        quantity_left_to_allocate -= quantity_to_take_from_batch

    if quantity_left_to_allocate > 0:
        raise ValidationError(
            f"Внутренняя ошибка при списании партий для товара '{product_to_sell.name}'."
        )

    if quantity_to_sell > 0:
        calculated_cost = (cost_for_this_sale_total / Decimal(str(quantity_to_sell))).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        order_item.cost_price_at_sale = calculated_cost
    else:
        order_item.cost_price_at_sale = Decimal('0.00')

def revert_fifo_write_off(order_item):
    """
    Возвращает списанный товар обратно в партии для одной позиции заказа.
    """
    product = order_item.product
    quantity_to_return = order_item.quantity

    batches = SupplyItem.objects.filter(
        product=product,
        supply__status='received'
    ).order_by('-supply__receipt_date', '-pk')

    left = quantity_to_return
    for batch in batches:
        max_return = batch.quantity_received - batch.quantity_remaining_in_batch
        to_return = min(left, max_return)
        if to_return > 0:
            batch.quantity_remaining_in_batch += to_return
            batch.save(update_fields=['quantity_remaining_in_batch'])
            left -= to_return
        if left == 0:
            break
    # Можно добавить проверку, если left > 0 — значит что-то не так (например, возврат больше, чем было списано)

def reserve_fifo_stock(order_item):
    """
    Резервирует товар по FIFO — увеличивает reserved_quantity у партий, не трогая реальные остатки.
    УЧИТЫВАЕТ, что при редактировании заказа нужно освободить старые резервы этого товара.
    """
    from suppliers.models import SupplyItem
    from orders.models import OrderProductItem
    
    product_to_reserve = order_item.product
    quantity_to_reserve = order_item.quantity

    if not product_to_reserve or quantity_to_reserve is None or quantity_to_reserve <= 0:
        return

    # НОВАЯ ЛОГИКА: Если это редактирование заказа, сначала снимаем старые резервы этого товара
    if order_item.pk:  # Если товар уже существует в заказе
        # Находим старое количество этого товара в заказе
        try:
            old_item = OrderProductItem.objects.get(pk=order_item.pk)
            old_quantity = old_item.quantity or 0
            # Временно освобождаем старые резервы
            if old_quantity > 0:
                temp_item = OrderProductItem(product=product_to_reserve, quantity=old_quantity)
                unreserve_fifo_stock(temp_item)
        except OrderProductItem.DoesNotExist:
            pass  # Новый товар, старых резервов нет

    # Теперь резервируем новое количество
    available_batches = SupplyItem.objects.filter(
        product=product_to_reserve,
        quantity_remaining_in_batch__gt=0
    ).order_by('supply__receipt_date', 'pk')

    quantity_left = quantity_to_reserve
    reserved_in_batches = []  # Запоминаем, что зарезервировали (на случай отката)
    
    for batch in available_batches:
        if quantity_left <= 0:
            break
        free_in_batch = batch.quantity_remaining_in_batch - batch.reserved_quantity
        qty = min(quantity_left, free_in_batch)
        if qty > 0:
            batch.reserved_quantity += qty
            batch.save(update_fields=['reserved_quantity'])
            reserved_in_batches.append((batch, qty))  # Запоминаем для возможного отката
            quantity_left -= qty

    # Если не хватает товара, откатываем все резервы и показываем ошибку
    if quantity_left > 0:
        # Откатываем все что зарезервировали
        for batch, qty in reserved_in_batches:
            batch.reserved_quantity -= qty
            batch.save(update_fields=['reserved_quantity'])
        
        from django.core.exceptions import ValidationError
        raise ValidationError(
            f"Недостаточно товара '{product_to_reserve.name}' для резервации {quantity_to_reserve} шт. "
            f"Доступно для резервации: {quantity_to_reserve - quantity_left} шт."
        )

def unreserve_fifo_stock(order_item):
    """
    Снимает резерв — уменьшает reserved_quantity у партий в обратном порядке (LIFO, чтобы удобнее было снимать).
    """
    from suppliers.models import SupplyItem
    product = order_item.product
    quantity_to_unreserve = order_item.quantity

    batches = SupplyItem.objects.filter(
        product=product,
        reserved_quantity__gt=0
    ).order_by('-supply__receipt_date', '-pk')

    left = quantity_to_unreserve
    for batch in batches:
        if left <= 0:
            break
        qty = min(left, batch.reserved_quantity)
        if qty > 0:
            batch.reserved_quantity -= qty
            batch.save(update_fields=['reserved_quantity'])
            left -= qty