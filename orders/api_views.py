# orders/api_views.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required # или staff_member_required
from decimal import Decimal, ROUND_HALF_UP

from products.models import Product
from suppliers.models import SupplyItem # Импортируем SupplyItem
from django.db.models import Sum # <--- ДОБАВЬ ЭТОТ ИМПОРТ

@login_required # Или staff_member_required, если доступ только для персонала
@require_GET # Принимаем только GET-запросы
def calculate_fifo_cost_api_view(request):
    product_id = request.GET.get('product_id')
    quantity_str = request.GET.get('quantity')

    if not product_id or not quantity_str:
        return JsonResponse({'error': 'Product ID and quantity are required.'}, status=400)

    try:
        product_id = int(product_id)
        quantity_to_estimate = Decimal(quantity_str)
        if quantity_to_estimate <= 0:
            return JsonResponse({'estimated_fifo_cost': '0.00', 'sufficient_stock': True, 'message': 'Quantity must be positive.'})
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid Product ID or quantity format.'}, status=400)

    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found.'}, status=404)

    # --- Логика "виртуального" FIFO-расчета ---
    # Эта логика очень похожа на твою calculate_and_assign_fifo_cost,
    # но БЕЗ сохранения изменений в batch.save()
    
    available_batches = SupplyItem.objects.filter(
        product=product,
        quantity_remaining_in_batch__gt=0
    ).order_by('supply__receipt_date', 'pk')

    total_quantity_in_batches = available_batches.aggregate(
        total_remaining=Sum('quantity_remaining_in_batch')
    )['total_remaining'] or Decimal('0.00')

    if total_quantity_in_batches < quantity_to_estimate:
        return JsonResponse({
            'estimated_fifo_cost': '0.00', # Или можно вернуть последнюю известную себестоимость
            'sufficient_stock': False,
            'available_stock': str(total_quantity_in_batches),
            'message': f'Insufficient stock. Available: {total_quantity_in_batches}, Requested: {quantity_to_estimate}'
        })

    cost_for_this_estimate_total = Decimal('0.00')
    quantity_left_to_allocate = quantity_to_estimate
    
    simulated_batches_info = [] # Для отладки, если нужно

    for batch in available_batches:
        if quantity_left_to_allocate <= Decimal('0.00'):
            break

        # ВАЖНО: Мы не можем использовать Decimal для quantity_remaining_in_batch напрямую, если оно IntegerField
        # Поэтому при сравнении и вычитании нужно быть аккуратным с типами или приводить
        current_batch_remaining_decimal = Decimal(str(batch.quantity_remaining_in_batch))
        quantity_to_take_from_batch = min(quantity_left_to_allocate, current_batch_remaining_decimal)
        
        cost_for_this_portion = quantity_to_take_from_batch * batch.cost_price_per_unit
        cost_for_this_estimate_total += cost_for_this_portion
        
        # НЕ СОХРАНЯЕМ ИЗМЕНЕНИЯ В BATCH
        # batch.quantity_remaining_in_batch -= int(quantity_to_take_from_batch) # Пример, если бы сохраняли
        # batch.save()
        
        simulated_batches_info.append(
            f"Took {quantity_to_take_from_batch} from batch {batch.id} (cost {batch.cost_price_per_unit})"
        )
        quantity_left_to_allocate -= quantity_to_take_from_batch

    if quantity_left_to_allocate > Decimal('0.00'):
        # Эта ситуация не должна возникнуть при правильной предварительной проверке
        return JsonResponse({'error': 'Internal error during FIFO simulation.'}, status=500)

    estimated_fifo_cost_str = '0.00'
    if quantity_to_estimate > 0:
        avg_fifo_cost = (cost_for_this_estimate_total / quantity_to_estimate).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        estimated_fifo_cost_str = str(avg_fifo_cost)
    
    return JsonResponse({
        'product_id': product_id,
        'requested_quantity': str(quantity_to_estimate),
        'estimated_fifo_cost': estimated_fifo_cost_str,
        'sufficient_stock': True,
        'available_stock': str(total_quantity_in_batches),
        'simulated_batches_info': simulated_batches_info # Для отладки
    })