# F:\CRM 2.0\ERP\reports\services.py (НОВЫЙ ФАЙЛ)

from decimal import Decimal
from django.db.models import F, Sum, DecimalField, ExpressionWrapper

# Важно: импортируем модели из их приложений
from suppliers.models import SupplyItem
from products.models import Product

def calculate_stock_report_data_fifo():
    """
    Рассчитывает ключевые показатели для сводного отчета по остаткам,
    используя FIFO-логику для себестоимости.
    
    Возвращает словарь с данными:
    - total_cost_fifo: Общая себестоимость всех товаров по партиям.
    - total_retail_value: Общая розничная стоимость всех товаров.
    - expected_profit: Ожидаемая прибыль (розничная стоимость - FIFO себестоимость).
    """
    
    # 1. Рассчитываем общую себестоимость по FIFO.
    # Это самый важный и правильный расчет. Мы суммируем стоимость остатка каждой партии.
    cost_aggregation = SupplyItem.objects.filter(
        quantity_remaining_in_batch__gt=0
    ).aggregate(
        total_cost=Sum(
            F('quantity_remaining_in_batch') * F('cost_price_per_unit'),
            output_field=DecimalField()
        )
    )
    total_cost_fifo = cost_aggregation.get('total_cost') or Decimal('0.00')

    # 2. Рассчитываем общую розничную стоимость.
    # Здесь логика не меняется, но делаем расчет централизованно.
    retail_aggregation = Product.objects.filter(
        stock_quantity__gt=0
    ).aggregate(
        total_retail=Sum(
            F('stock_quantity') * F('retail_price'),
            output_field=DecimalField()
        )
    )
    total_retail_value = retail_aggregation.get('total_retail') or Decimal('0.00')

    # 3. Рассчитываем ожидаемую прибыль как разницу двух итоговых сумм.
    expected_profit = total_retail_value - total_cost_fifo

    return {
        'total_cost_fifo': total_cost_fifo.quantize(Decimal('0.01')),
        'total_retail_value': total_retail_value.quantize(Decimal('0.01')),
        'expected_profit': expected_profit.quantize(Decimal('0.01')),
    }