# CRM 2.0/ERP/orders/views.py
from django.http import JsonResponse
from .models import Service # Импортируем модель Service из текущего приложения
from django.views.decorators.http import require_GET # Будем использовать GET-запрос
from .models import OrderType # Убедись, что OrderType импортирован

def get_service_price(request, service_id):
    """
    Представление для получения цены услуги по её ID.
    Возвращает JSON с ценой или ошибку, если услуга не найдена.
    """
    try:
        service = Service.objects.get(pk=service_id)
        data = {
            'price': str(service.price) # Конвертируем Decimal в строку для JSON
        }
        return JsonResponse(data)
    except Service.DoesNotExist:
        return JsonResponse({'error': 'Service not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# Если в этом файле views.py есть другие представления, оставьте их.
# Этот код добавляется к существующему содержимому или создает файл, если его не было.

@require_GET # Наш API будет принимать только GET-запросы
def determine_order_type_api_view(request):
    has_products_str = request.GET.get('has_products', 'false').lower()
    has_services_str = request.GET.get('has_services', 'false').lower()

    has_products = has_products_str == 'true'
    has_services = has_services_str == 'true'

    # Имена типов заказа, как они у тебя заданы в базе данных
    repair_type_name = "Ремонт"
    sale_type_name = "Продажа"
    undefined_type_name = "Определить"

    determined_type_name = undefined_type_name 
    determined_type_id = None

    try:
        if has_services:
            actual_type = OrderType.objects.filter(name=repair_type_name).first()
            if actual_type:
                determined_type_name = actual_type.name
                determined_type_id = actual_type.id
        elif has_products: # Услуг нет, но есть товары
            actual_type = OrderType.objects.filter(name=sale_type_name).first()
            if actual_type:
                determined_type_name = actual_type.name
                determined_type_id = actual_type.id
        
        # Если после логики выше ID не определен (например, нет ни товаров, ни услуг, 
        # или не найдены типы "Ремонт"/"Продажа"), то ищем тип "Определить"
        if determined_type_id is None:
            actual_type = OrderType.objects.filter(name=undefined_type_name).first()
            if actual_type:
                determined_type_name = actual_type.name
                determined_type_id = actual_type.id
            else:
                # Критическая ситуация: даже тип "Определить" не найден.
                # Это означает проблему с базовыми данными OrderType.
                print(f"Критическая ошибка: Тип заказа '{undefined_type_name}' не найден в базе данных.")
                return JsonResponse({'error': f"Базовый тип заказа '{undefined_type_name}' не настроен."}, status=500)

        return JsonResponse({
            'order_type_id': determined_type_id,
            'order_type_name': determined_type_name
        })

    except Exception as e:
        print(f"Ошибка в determine_order_type_api_view: {str(e)}") # Логирование ошибки
        return JsonResponse({'error': 'Внутренняя ошибка сервера при определении типа заказа.'}, status=500)