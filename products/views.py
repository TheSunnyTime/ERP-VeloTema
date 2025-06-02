# F:\CRM 2.0\ERP\products\views.py
from django.http import JsonResponse
from .models import Product 
from decimal import Decimal # Импортируем Decimal для проверки на None

def get_product_price_api_view(request, product_id): # Переименовал для единообразия с другими API view
    """
    Представление для получения розничной цены, остатка и себестоимости продукта по его ID.
    Возвращает JSON или ошибку, если продукт не найден.
    """
    try:
        product = Product.objects.get(pk=product_id)
        
        # Убедимся, что cost_price не None перед конвертацией в строку
        cost_price_str = str(product.cost_price) if product.cost_price is not None else None
        
        data = {
            'retail_price': str(product.retail_price),   # Розничная цена
            'stock_quantity': product.stock_quantity,    # Текущий остаток
            'cost_price': cost_price_str                 # Базовая себестоимость из карточки товара
        }
        return JsonResponse(data)
    except Product.DoesNotExist:
        return JsonResponse({
            'error': 'Product not found', 
            'retail_price': '0.00', # Возвращаем строки, чтобы JS не падал
            'stock_quantity': 0,
            'cost_price': '0.00'  # Возвращаем строки
        }, status=404)
    except Exception as e:
        # В реальном проекте здесь лучше логировать ошибку e
        print(f"Error in get_product_price_api_view: {e}") # Для отладки
        return JsonResponse({
            'error': 'Server error', 
            'retail_price': '0.00', 
            'stock_quantity': 0,
            'cost_price': '0.00'
        }, status=500)

# Если у тебя в этом файле есть другие view, оставь их как есть.
# Эта функция заменяет или создает get_product_price (или с новым именем get_product_price_api_view).