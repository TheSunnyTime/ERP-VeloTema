# F:\CRM 2.0\ERP\products\views.py
from django.http import JsonResponse
from .models import Product 

def get_product_price(request, product_id):
    """
    Представление для получения розничной цены и остатка продукта по его ID.
    Возвращает JSON с ценой и остатком или ошибку, если продукт не найден.
    """
    try:
        product = Product.objects.get(pk=product_id)
        data = {
            'retail_price': str(product.retail_price),  # Конвертируем Decimal в строку
            'stock_quantity': product.stock_quantity   # Добавляем остаток (обычно это Integer)
        }
        return JsonResponse(data)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found', 'retail_price': '', 'stock_quantity': ''}, status=404) # Добавим пустые значения для JS
    except Exception as e:
        # В реальном проекте здесь лучше логировать ошибку e
        return JsonResponse({'error': str(e), 'retail_price': '', 'stock_quantity': ''}, status=500) # Добавим пустые значения