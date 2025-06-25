# F:\CRM 2.0\ERP\products\views.py

# --- Старые импорты, которые уже были ---
from django.http import JsonResponse
from .models import Product 
from decimal import Decimal # Импортируем Decimal для проверки на None

# --- Новые импорты, которые нам понадобятся для поиска ---
from django.contrib.auth.decorators import login_required
from .search_utils import get_product_search_queryset, format_product_for_display


# --- СУЩЕСТВУЮЩИЙ VIEW ---
# Этот view ты прислал. Он нужен для получения цены и остатка уже выбранного товара.
# Мы его не трогаем, он работает правильно и выполняет свою задачу.
def get_product_price_api_view(request, product_id):
    """
    Представление для получения розничной цены, остатка и себестоимости продукта по его ID.
    Возвращает JSON или ошибку, если продукт не найден.
    """
    try:
        product = Product.objects.get(pk=product_id)
        
        # Убедимся, что cost_price не None перед конвертацией в строку
        cost_price_str = str(product.cost_price) if product.cost_price is not None else None
        
        data = {
            'retail_price': str(product.retail_price),  # Розничная цена
            'stock_quantity': product.get_available_stock_quantity(), # Доступный остаток (правильный расчет)
            'cost_price': cost_price_str                    # Базовая себестоимость из карточки товара
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


# --- НАШ НОВЫЙ VIEW ДЛЯ ПОИСКА ---
# Мы добавляем этот view в твой файл. Он будет обрабатывать поисковые запросы от Select2.
@login_required
def product_autocomplete(request):
    """
    View для автодополнения (поиска) товаров, который будет использоваться в Select2.
    """
    # Получаем поисковый запрос из параметра 'q' в URL
    q = request.GET.get('q', '')
    
    # Используем нашу новую, улучшенную функцию поиска из search_utils.py
    products = get_product_search_queryset(
        Product.objects.all(), 
        q
    )
    
    # Ограничиваем количество результатов, чтобы не перегружать страницу
    products = products[:20] 
    
    # Форматируем результаты в виде, который понимает Select2
    results = []
    for product in products:
        results.append({
            'id': product.id,
            'text': format_product_for_display(product),
        })
        
    return JsonResponse({'results': results})