# F:\CRM 2.0\erp\orders\admin\order_inlines_admin.py
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from decimal import Decimal

# Относительный импорт моделей из текущего приложения orders
from ..models import OrderProductItem, OrderServiceItem, Order 

# Вспомогательная функция для получения родительского заказа
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
    # formset = BaseOrderProductItemFormSet # Убедись, что BaseOrderProductItemFormSet определен в orders/forms.py и импортирован, если используется
    extra = 0 # Показываем одну пустую форму по умолчанию
    autocomplete_fields = ['product']
    fields = ('product', 'get_current_stock', 'quantity', 
              'price_at_order', 'cost_price_at_sale', 'display_item_total')
    
    def get_current_stock(self, obj):
        if obj.product: return obj.product.stock_quantity
        return "N/A"
    get_current_stock.short_description = "На складе (тек.)"

    def display_item_total(self, obj):
        if obj.pk: return obj.get_item_total()
        return Decimal('0.00')
    display_item_total.short_description = "Сумма по строке"

    def get_readonly_fields(self, request, obj=None):
        # obj здесь это экземпляр OrderProductItem, если он существует, иначе None
        # родительский Order получаем через get_parent_order_from_request
        readonly = ['get_current_stock', 'display_item_total', 'cost_price_at_sale'] # cost_price_at_sale теперь readonly
        if not request.user.is_superuser: 
            readonly.append('price_at_order')
        
        parent_order = get_parent_order_from_request(request, obj) # Передаем obj (инлайн-объект)
        if parent_order and parent_order.status == Order.STATUS_ISSUED:
            readonly.extend(['product', 'quantity', 'price_at_order'])
        return tuple(set(readonly))

    def has_add_permission(self, request, obj=None): # obj здесь это родительский Order
        parent_order = obj # В has_add_permission obj - это родительский объект (Order)
        if parent_order and parent_order.status == Order.STATUS_ISSUED: 
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None): # obj здесь это OrderProductItem
        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status == Order.STATUS_ISSUED: 
            return False
        return super().has_delete_permission(request, obj)

class OrderServiceItemInline(admin.TabularInline):
    model = OrderServiceItem
    extra = 0 # Показываем одну пустую форму по умолчанию
    autocomplete_fields = ['service']
    fields = ('service', 'quantity', 'price_at_order', 'display_item_total')

    def display_item_total(self, obj):
        if obj.pk: return obj.get_item_total()
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

    def has_add_permission(self, request, obj=None): # obj здесь это родительский Order
        parent_order = obj
        if parent_order and parent_order.status == Order.STATUS_ISSUED: 
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None): # obj здесь это OrderServiceItem
        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status == Order.STATUS_ISSUED: 
            return False
        return super().has_delete_permission(request, obj)