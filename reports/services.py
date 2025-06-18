# F:\CRM 2.0\ERP\reports\services.py (НОВЫЙ ФАЙЛ)

from decimal import Decimal
from django.db.models import F, Sum, DecimalField, ExpressionWrapper

# Важно: импортируем модели из их приложений
from suppliers.models import SupplyItem
from products.models import Product

def calculate_stock_report_data_fifo():
    """
    Рассчитывает ключевые показатели для сводного отчета по остаткам,
    используя FIFO-логику для себестоимости + добавляет данные о резервах.
    
    Возвращает словарь с данными:
    - total_cost_fifo: Общая себестоимость всех ДОСТУПНЫХ товаров (не зарезервированных).
    - total_retail_value: Общая розничная стоимость всех ДОСТУПНЫХ товаров.
    - expected_profit: Ожидаемая прибыль (розничная стоимость - FIFO себестоимость).
    - products_data: Список товаров с подробной информацией (включая резервы).
    """
    
    # Импортируем модели для подсчета резервов
    from orders.models import OrderProductItem, Order
    from django.db.models import Q
    
    # Получаем все товары с остатками больше 0
    products_with_stock = Product.objects.filter(stock_quantity__gt=0).order_by('name')
    
    products_data = []
    total_cost_fifo = Decimal('0.00')
    total_retail_value = Decimal('0.00')
    
    for product in products_with_stock:
        # 1. Получаем данные о товаре
        stock_quantity = product.stock_quantity
        retail_price = product.retail_price
        
        # 2. Считаем резерв товара (товары в заказах кроме "Выдан" и "Отменен")
        reserved_query = OrderProductItem.objects.filter(
            product=product
        ).exclude(
            Q(order__status=Order.STATUS_ISSUED) | Q(order__status=Order.STATUS_CANCELLED)
        )
        
        reserved_sum = reserved_query.aggregate(total_reserved=Sum('quantity'))
        total_reserved = reserved_sum.get('total_reserved') or 0
        
        # 3. Считаем доступное количество (остаток - резерв)
        available_quantity = max(0, stock_quantity - total_reserved)
        
        # 4. Считаем себестоимость ДОСТУПНОГО количества по FIFO
        if available_quantity > 0:
            # Получаем партии товара с остатками, отсортированные по дате поступления (FIFO)
            available_batches = SupplyItem.objects.filter(
                product=product,
                quantity_remaining_in_batch__gt=0
            ).order_by('supply__receipt_date', 'pk')
            
            # Считаем себестоимость для доступного количества
            cost_for_available = Decimal('0.00')
            quantity_left = available_quantity
            
            for batch in available_batches:
                if quantity_left <= 0:
                    break
                    
                # Берем минимум из того, что нужно и что есть в партии
                qty_from_batch = min(quantity_left, batch.quantity_remaining_in_batch)
                cost_for_available += qty_from_batch * batch.cost_price_per_unit
                quantity_left -= qty_from_batch
                
            fifo_cost_per_unit = cost_for_available / available_quantity if available_quantity > 0 else Decimal('0.00')
        else:
            cost_for_available = Decimal('0.00')
            fifo_cost_per_unit = Decimal('0.00')
        
        # 5. Считаем розничную стоимость доступного количества
        retail_value_available = available_quantity * retail_price
        
        # 6. Добавляем к общим итогам (только доступные товары)
        total_cost_fifo += cost_for_available
        total_retail_value += retail_value_available
        
        # 7. Сохраняем данные о товаре для отображения в таблице
        products_data.append({
            'product': product,
            'stock_quantity': stock_quantity,
            'reserved_quantity': total_reserved,
            'available_quantity': available_quantity,
            'fifo_cost_per_unit': fifo_cost_per_unit.quantize(Decimal('0.01')),
            'retail_price': retail_price,
            'total_cost_available': cost_for_available.quantize(Decimal('0.01')),
            'total_retail_available': retail_value_available.quantize(Decimal('0.01')),
        })
    
    # 8. Считаем ожидаемую прибыль
    expected_profit = total_retail_value - total_cost_fifo
    
    return {
        'total_cost_fifo': total_cost_fifo.quantize(Decimal('0.01')),
        'total_retail_value': total_retail_value.quantize(Decimal('0.01')),
        'expected_profit': expected_profit.quantize(Decimal('0.01')),
        'products_data': products_data,  # НОВОЕ: подробные данные по каждому товару
    }