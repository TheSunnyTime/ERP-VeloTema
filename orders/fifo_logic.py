from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Sum, F
from django.core.exceptions import ValidationError
from suppliers.models import SupplyItem

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

    # Ищем партии где есть свободный товар (не зарезервированный)
    available_batches = SupplyItem.objects.filter(
        product=product_to_sell,
        quantity_remaining_in_batch__gt=0,
        supply__status='received'  # Только принятые поставки!
    ).order_by('supply__receipt_date', 'pk')

    print(f"ОТЛАДКА ВИРТУАЛ: Товар {product_to_sell.name} - ищем партии для бронирования {quantity_to_sell}")
    for batch in available_batches:
        free_qty = batch.quantity_remaining_in_batch - batch.reserved_quantity
        print(f"ОТЛАДКА ВИРТУАЛ: Партия {batch.id} - остаток={batch.quantity_remaining_in_batch}, резерв={batch.reserved_quantity}, свободно={free_qty}")

    # Считаем сколько товара реально доступно (без резерва)
    total_quantity_in_batches = Decimal('0.00')
    for batch in available_batches:
        free_in_batch = batch.quantity_remaining_in_batch - batch.reserved_quantity
        if free_in_batch > 0:
            total_quantity_in_batches += free_in_batch

    print(f"ОТЛАДКА ВИРТУАЛ: Всего свободного товара {product_to_sell.name} = {total_quantity_in_batches}")

    if total_quantity_in_batches < quantity_to_sell:
        # Если товар уже есть в заказе - разрешаем подсчет цены
        if hasattr(order_item, 'pk') and order_item.pk:
            print(f"ПРЕДУПРЕЖДЕНИЕ: Товар '{product_to_sell.name}' закончился, но уже есть в заказе")
            print(f"Устанавливаем цену товара равной нулю")
            order_item.cost_price_at_sale = Decimal('0.00')
            return
        else:
            # Новый товар - показываем ошибку
            raise ValidationError(
                f"Недостаточно товара '{product_to_sell.name}' на складе для бронирования {quantity_to_sell} шт. "
                f"Доступно: {total_quantity_in_batches}."
            )

    cost_for_this_sale_total = Decimal('0.00')
    quantity_left = Decimal(str(quantity_to_sell))
    for batch in available_batches:
        if quantity_left <= 0:
            break
        # Учитываем только свободное количество (без резерва)
        free_in_batch = batch.quantity_remaining_in_batch - batch.reserved_quantity
        qty = min(quantity_left, Decimal(str(free_in_batch)))
        if qty > 0:
            cost_for_this_sale_total += qty * batch.cost_price_per_unit
            quantity_left -= qty
            print(f"ОТЛАДКА ВИРТУАЛ: Из партии {batch.id} берем {qty} по цене {batch.cost_price_per_unit}")

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

    # Проверяем входные данные
    if not product_to_reserve:
        return
        
    # Если количество 0 или отрицательное - просто выходим без ошибки
    if quantity_to_reserve is None or quantity_to_reserve <= 0:
        print(f"ОТЛАДКА РЕЗЕРВ: Количество товара {product_to_reserve.name} = {quantity_to_reserve}, пропускаем резервирование")
        return
    

    # Проверяем - возможно товар помечен на удаление
    if hasattr(order_item, '_state') and getattr(order_item, 'DELETE', False):
        print(f"ОТЛАДКА РЕЗЕРВ: Товар {product_to_reserve.name} помечен на удаление, пропускаем резервирование")
        return
    # НОВАЯ ЛОГИКА: Если это редактирование заказа, сначала снимаем старые резервы этого товара
    if order_item.pk:  # Если товар уже существует в заказе
        # Находим старое количество этого товара в заказе
        try:
            # Получаем данные из базы данных, а не из текущего объекта
            old_item = OrderProductItem.objects.select_for_update().get(pk=order_item.pk)
            old_quantity = old_item.quantity or 0
            print(f"ОТЛАДКА РЕЗЕРВ: Товар {product_to_reserve.name} уже в заказе. Старое количество: {old_quantity}, новое: {quantity_to_reserve}")
            
            # Временно освобождаем старые резервы
            if old_quantity > 0:
                temp_item = OrderProductItem(product=product_to_reserve, quantity=old_quantity)
                unreserve_fifo_stock(temp_item)
                print(f"ОТЛАДКА РЕЗЕРВ: Освободили резерв {old_quantity} для {product_to_reserve.name}")
        except OrderProductItem.DoesNotExist:
            print(f"ОТЛАДКА РЕЗЕРВ: Новый товар {product_to_reserve.name}, старых резервов нет")

    # Теперь резервируем новое количество
    available_batches = SupplyItem.objects.filter(
        product=product_to_reserve,
        quantity_remaining_in_batch__gt=0,
        supply__status='received'  # Только принятые поставки!
    ).order_by('supply__receipt_date', 'pk')

    print(f"ОТЛАДКА РЕЗЕРВ: Начинаем резервировать {quantity_to_reserve} для {product_to_reserve.name}")
    print(f"ОТЛАДКА РЕЗЕРВ: Найдено партий с остатками: {available_batches.count()}")

    # Проверяем ВСЕ партии этого товара (включая пустые)
    all_batches = SupplyItem.objects.filter(product=product_to_reserve)
    print(f"ОТЛАДКА РЕЗЕРВ: Всего партий товара (включая пустые): {all_batches.count()}")

    for i, batch in enumerate(all_batches):
        print(f"ОТЛАДКА РЕЗЕРВ: Партия {i+1} (ID={batch.id}): получено={batch.quantity_received}, остаток={batch.quantity_remaining_in_batch}, резерв={batch.reserved_quantity}")
    
    quantity_left = quantity_to_reserve
    reserved_in_batches = []  # Запоминаем, что зарезервировали (на случай отката)
    
    for batch in available_batches:
        if quantity_left <= 0:
            break
        free_in_batch = batch.quantity_remaining_in_batch - batch.reserved_quantity
        print(f"ОТЛАДКА РЕЗЕРВ: Партия {batch.id} - остаток={batch.quantity_remaining_in_batch}, резерв={batch.reserved_quantity}, свободно={free_in_batch}")
        
        qty = min(quantity_left, free_in_batch)
        if qty > 0:
            batch.reserved_quantity += qty
            batch.save(update_fields=['reserved_quantity'])
            reserved_in_batches.append((batch, qty))  # Запоминаем для возможного отката
            quantity_left -= qty
            print(f"ОТЛАДКА РЕЗЕРВ: Зарезервировали {qty} в партии {batch.id}")

    # Если не хватает товара, откатываем все резервы и показываем ошибку
    if quantity_left > 0:
        # Откатываем все что зарезервировали
        for batch, qty in reserved_in_batches:
            batch.reserved_quantity -= qty
            batch.save(update_fields=['reserved_quantity'])
        
        print(f"ОТЛАДКА РЕЗЕРВ: ОШИБКА! Недостаточно товара {product_to_reserve.name} для резерва {quantity_to_reserve}")
        print(f"ОТЛАДКА РЕЗЕРВ: Доступно только: {quantity_to_reserve - quantity_left}")
        
        # Проверяем есть ли вообще этот товар на складе
        total_stock = product_to_reserve.get_real_stock_quantity
        print(f"ОТЛАДКА РЕЗЕРВ: Общий остаток товара {product_to_reserve.name} = {total_stock}")

        # Проверяем есть ли партии этого товара
        all_batches = SupplyItem.objects.filter(product=product_to_reserve)
        print(f"ОТЛАДКА РЕЗЕРВ: Всего партий товара {product_to_reserve.name} = {all_batches.count()}")

        # Проверяем реальные остатки в партиях
        real_stock_in_batches = 0
        for batch in all_batches:
            real_stock_in_batches += batch.quantity_remaining_in_batch

        print(f"ОТЛАДКА РЕЗЕРВ: Реальный остаток в партиях = {real_stock_in_batches}")

        if real_stock_in_batches == 0:
            print(f"ОТЛАДКА РЕЗЕРВ: ОШИБКА! Товара {product_to_reserve.name} реально нет на складе")
            # Если товар уже был в заказе - просто показываем предупреждение, но разрешаем сохранить
            if order_item.pk:  # Товар уже существует в заказе
                print(f"ПРЕДУПРЕЖДЕНИЕ: Товар '{product_to_reserve.name}' закончился на складе, но уже есть в заказе")
                print(f"Позволяем сохранить заказ для возможности редактирования")
                return  # Выходим без ошибки
            else:
                # Новый товар - показываем ошибку
                raise ValidationError(
                    f"Товар '{product_to_reserve.name}' закончился на складе. "
                    f"Реальный остаток в партиях: {real_stock_in_batches} шт. "
                    f"Нельзя добавить новый товар в заказ."
                )
        elif total_stock == 0 or all_batches.count() == 0:
            print(f"ОТЛАДКА РЕЗЕРВ: ОШИБКА! Товара {product_to_reserve.name} нет на складе")
            raise ValidationError(
                f"Товар '{product_to_reserve.name}' отсутствует на складе. "
                f"Нельзя добавить его в заказ. Остаток: {total_stock} шт."
            )
        else:
            # Если товар есть, но весь зарезервирован
            raise ValidationError(
                f"Недостаточно товара '{product_to_reserve.name}' для резервации {quantity_to_reserve} шт. "
                f"Свободно для резервации: {quantity_to_reserve - quantity_left} шт."
            )


def unreserve_fifo_stock(order_item):
    """
    Снимает резерв по FIFO — убирает reserved_quantity у партий только на то количество, что было зарезервировано под этот заказ.
    """
    from suppliers.models import SupplyItem
    from orders.models import OrderProductItem

    product = order_item.product
    quantity_to_unreserve = order_item.quantity or 0

    print(f"ОТЛАДКА СНЯТИЕ РЕЗЕРВА: Снимаем резерв {quantity_to_unreserve} для товара {product.name}")

    if quantity_to_unreserve <= 0:
        print(f"ОТЛАДКА СНЯТИЕ РЕЗЕРВА: Количество для снятия резерва <= 0, выходим")
        return

    # Снимаем резерв с партий в том же порядке, в каком резервировали (FIFO)
    batches = SupplyItem.objects.filter(
        product=product,
        reserved_quantity__gt=0,
        supply__status='received'
    ).order_by('supply__receipt_date', 'pk')

    left = quantity_to_unreserve

    for batch in batches:
        if left <= 0:
            break
        to_unreserve = min(batch.reserved_quantity, left)
        if to_unreserve > 0:
            print(f"ОТЛАДКА СНЯТИЕ РЕЗЕРВА: Партия {batch.id} - было резерва {batch.reserved_quantity}, снимаем {to_unreserve}")
            batch.reserved_quantity -= to_unreserve
            batch.save(update_fields=['reserved_quantity'])
            left -= to_unreserve

    if left > 0:
        print(f"ОТЛАДКА СНЯТИЕ РЕЗЕРВА: ВНИМАНИЕ! Не удалось снять {left} из резерва (в партиях не хватило резерва)")
    else:
        print(f"ОТЛАДКА СНЯТИЕ РЕЗЕРВА: Резерв полностью снят")