# F:\CRM 2.0\ERP\reports\exports.py

from django.http import HttpResponse
import csv
from products.models import Product
from orders.models import OrderProductItem, Order
from django.db.models import Sum, Q

def export_stock_csv(request):
    """
    Экспорт остатков товаров в CSV формат
    Доступно по ссылке без авторизации для торговых площадок
    Фильтрует товары где доступно >= 1 (остаток минус резерв)
    """
    # Создаём HTTP ответ с типом CSV и русской кодировкой
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="stock_export.csv"'
    
    # Добавляем BOM для корректного отображения русских символов в Excel
    response.write('\ufeff')
    
    # Создаём CSV писатель с точкой запятой как разделитель
    writer = csv.writer(response, delimiter=';')
    
    # Пишем заголовки столбцов
    writer.writerow(['Артикул', 'Наименование', 'ОПТ', 'РЦ', 'Доступно'])
    
    # Получаем все товары где есть остаток на складе
    products = Product.objects.filter(stock_quantity__gt=0)
    
    # Проходим по каждому товару и добавляем в CSV
    for product in products:
        # Считаем резерв товара (товары в заказах кроме "Выдан" и "Отменен")
        reserved_query = OrderProductItem.objects.filter(
            product=product
        ).exclude(
            Q(order__status=Order.STATUS_ISSUED) | Q(order__status=Order.STATUS_CANCELLED)
        )
        
        reserved_sum = reserved_query.aggregate(total_reserved=Sum('quantity'))
        total_reserved = reserved_sum.get('total_reserved') or 0
        
        # Считаем доступное количество (остаток минус резерв)
        available_quantity = max(0, product.stock_quantity - total_reserved)
        
        # Пропускаем товары где доступно меньше 1
        if available_quantity < 1:
            continue
            
        # Добавляем строку с данными товара
        writer.writerow([
            product.sku or '',                    # Артикул (если нет - пустая строка)
            product.name,                         # Наименование товара
            str(product.cost_price),              # ОПТ (себестоимость)
            str(product.retail_price),            # РЦ (розничная цена)
            str(available_quantity)               # Доступно (остаток минус резерв)
        ])
    
    return response