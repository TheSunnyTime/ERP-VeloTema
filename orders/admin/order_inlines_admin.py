# F:\CRM 2.0\erp\orders\admin\order_inlines_admin.py
from django.contrib import admin
# from django.urls import reverse # reverse здесь не используется
from django.utils.html import format_html
from decimal import Decimal

# Относительный импорт моделей из текущего приложения orders
from ..models import OrderProductItem, OrderServiceItem, Order

# Вспомогательная функция для получения родительского заказа
# (оставляем без изменений, если она тебе нужна и работает корректно)
def get_parent_order_from_request(request, obj_inline=None):
    if obj_inline and obj_inline.pk and hasattr(obj_inline, 'order'):
        return obj_inline.order
    
    resolver_match = request.resolver_match
    if resolver_match and 'object_id' in resolver_match.kwargs:
        parent_order_id = resolver_match.kwargs['object_id']
        if parent_order_id:
            try:
                return Order.objects.get(pk=parent_order_id)
            except Order.DoesNotExist:
                return None
    return None

class OrderProductItemInline(admin.TabularInline):
    model = OrderProductItem
    extra = 0 
    autocomplete_fields = ['product']
    
    # --- ИЗМЕНЕНИЯ ЗДЕСЬ (порядок полей и добавление нового) ---
    fields = (
        'product', 
        'get_current_stock', 
        'display_product_base_cost_price', # Новое поле для отображения базовой себестоимости
        'quantity', 
        'price_at_order',                  # Это цена продажи
        'cost_price_at_sale',              # Это поле для FIFO себестоимости (останется пустым до выдачи)
        'display_item_total'
    )
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---
    
    def get_current_stock(self, obj):
        if obj.product: return obj.product.stock_quantity
        return "N/A"
    get_current_stock.short_description = "На складе (тек.)"

    # --- НОВЫЙ МЕТОД для отображения Product.cost_price ---
    def display_product_base_cost_price(self, obj):
        # Этот метод будет вызываться Django при рендеринге формы.
        # JS будет перезаписывать это значение динамически.
        # Если товар уже выбран (например, при редактировании сохраненного заказа),
        # и это не новая пустая строка инлайна (проверяем по obj.pk)
        if obj.pk and obj.product and obj.product.cost_price is not None:
            return f"{obj.product.cost_price:.2f}" # Показываем, если товар уже выбран и сохранен
        return "---" # Плейсхолдер для новых строк или если себестоимость не задана
    display_product_base_cost_price.short_description = "Базовая себест. (справ.)"
    # --- КОНЕЦ НОВОГО МЕТОДА ---

    def display_item_total(self, obj):
        # Используем obj.get_item_total(), если он корректно возвращает Decimal
        # или рассчитываем здесь, если obj.pk еще нет (новая строка)
        if obj.pk: 
            return obj.get_item_total()
        elif obj.quantity is not None and obj.price_at_order is not None:
             try:
                return Decimal(obj.quantity) * Decimal(obj.price_at_order)
             except: # На случай, если price_at_order еще не Decimal
                return Decimal('0.00')
        return Decimal('0.00')
    display_item_total.short_description = "Сумма по строке"

    def get_readonly_fields(self, request, obj=None):
        readonly = [
            'get_current_stock', 
            'display_item_total', 
            'cost_price_at_sale', # FIFO себестоимость всегда readonly
            'display_product_base_cost_price' # Новое поле тоже readonly, заполняется JS
        ]
        if not request.user.is_superuser: 
            readonly.append('price_at_order')
        
        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status == Order.STATUS_ISSUED:
            readonly.extend(['product', 'quantity', 'price_at_order']) # Добавляем price_at_order еще раз на всякий случай
        
        # Возвращаем кортеж уникальных значений
        return tuple(set(readonly))

    def has_add_permission(self, request, obj=None):
        parent_order = obj 
        if parent_order and parent_order.status == Order.STATUS_ISSUED: 
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status == Order.STATUS_ISSUED: 
            return False
        return super().has_delete_permission(request, obj)

class OrderServiceItemInline(admin.TabularInline):
    model = OrderServiceItem
    extra = 0
    autocomplete_fields = ['service']
    fields = ('service', 'quantity', 'price_at_order', 'display_item_total')

    def display_item_total(self, obj):
        if obj.pk: 
            return obj.get_item_total()
        elif obj.quantity is not None and obj.price_at_order is not None:
            try:
                return Decimal(obj.quantity) * Decimal(obj.price_at_order)
            except:
                return Decimal('0.00')
        return Decimal('0.00')
    display_item_total.short_description = "Сумма по строке"

    def get_readonly_fields(self, request, obj=None):
        readonly = ['display_item_total']
        if not request.user.is_superuser: 
            readonly.append('price_at_order')
        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status == Order.STATUS_ISSUED:
            readonly.extend(['service', 'quantity', 'price_at_order'])
        return tuple(set(readonly))

    def has_add_permission(self, request, obj=None):
        parent_order = obj
        if parent_order and parent_order.status == Order.STATUS_ISSUED: 
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status == Order.STATUS_ISSUED: 
            return False
        return super().has_delete_permission(request, obj)