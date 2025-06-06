# F:\CRM 2.0\erp\orders\admin\order_inlines_admin.py
from django import forms # <--- Добавлен импорт forms
from django.contrib import admin
from django.utils.html import format_html
from decimal import Decimal

from ..models import OrderProductItem, OrderServiceItem, Order, Product, Service # <--- Добавлены Product и Service

# Вспомогательная функция (без изменений)
def get_parent_order_from_request(request, obj_inline=None):
    # ... (твой код без изменений) ...
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

# --- Кастомная форма для OrderProductItem ---
class OrderProductItemAdminForm(forms.ModelForm):
    class Meta:
        model = OrderProductItem
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        # Проверяем, что это существующий объект, есть товар и цена
        if instance and instance.pk and instance.product and instance.price_at_order is not None:
            try:
                # Получаем "стандартную" цену товара из справочника
                standard_price = instance.product.retail_price 
                # Сравниваем (Decimal поля)
                if instance.price_at_order != standard_price:
                    # Если цена в заказе отличается от стандартной, помечаем ее как введенную вручную
                    self.fields['price_at_order'].widget.attrs['data-manual-price'] = 'true'
                    # console.log(f"Product {instance.product.name}: price_at_order ({instance.price_at_order}) != standard_price ({standard_price}). Flag set.")
            except Product.DoesNotExist: # На всякий случай, если товар был удален, хотя ForeignKey PROTECT
                pass # Ничего не делаем, если товар не найден
            except Exception as e: # Ловим другие возможные ошибки
                print(f"Error in OrderProductItemAdminForm __init__ for product {instance.product_id}: {e}")


class OrderProductItemInline(admin.TabularInline):
    model = OrderProductItem
    form = OrderProductItemAdminForm # <--- Используем кастомную форму
    extra = 0 
    autocomplete_fields = ['product']
    
    fields = (
        'product', 
        'get_current_stock', 
        'display_product_base_cost_price',
        'quantity', 
        'price_at_order',
        'cost_price_at_sale',
        'display_item_total'
    )
    
    def get_current_stock(self, obj):
        if obj.product: return obj.product.stock_quantity
        return "N/A"
    get_current_stock.short_description = "На складе (тек.)"

    def display_product_base_cost_price(self, obj):
        if obj.pk and obj.product and obj.product.cost_price is not None:
            return f"{obj.product.cost_price:.2f}"
        return "---"
    display_product_base_cost_price.short_description = "Базовая себест. (справ.)"

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
        readonly = [
            'get_current_stock', 
            'display_item_total', 
            'cost_price_at_sale',
            'display_product_base_cost_price'
        ]
        # Разрешаем редактирование price_at_order для суперпользователя всегда,
        # если заказ не выдан. Для остальных - только если есть права (у тебя это не реализовано, но можно добавить)
        # Пока что, если не суперюзер, то price_at_order readonly, если заказ не выдан.
        # Это поведение можно изменить, если нужно, чтобы все могли редактировать цену до выдачи.
        # if not request.user.is_superuser: 
        #     readonly.append('price_at_order') 
        # УБРАЛ ЭТО УСЛОВИЕ, чтобы все могли редактировать цену, если заказ не выдан.
        # Флаг data-manual-price будет управлять перезаписью из JS.

        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status == Order.STATUS_ISSUED:
            # Если заказ выдан, все поля инлайна делаем readonly
            readonly.extend(['product', 'quantity', 'price_at_order'])
        
        return tuple(set(readonly))

    # has_add_permission и has_delete_permission без изменений

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

# --- Кастомная форма для OrderServiceItem ---
class OrderServiceItemAdminForm(forms.ModelForm):
    class Meta:
        model = OrderServiceItem
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.pk and instance.service and instance.price_at_order is not None:
            try:
                standard_price = instance.service.price
                if instance.price_at_order != standard_price:
                    self.fields['price_at_order'].widget.attrs['data-manual-price'] = 'true'
                    # console.log(f"Service {instance.service.name}: price_at_order ({instance.price_at_order}) != standard_price ({standard_price}). Flag set.")
            except Service.DoesNotExist:
                pass
            except Exception as e:
                print(f"Error in OrderServiceItemAdminForm __init__ for service {instance.service_id}: {e}")

class OrderServiceItemInline(admin.TabularInline):
    model = OrderServiceItem
    form = OrderServiceItemAdminForm # <--- Используем кастомную форму
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
        # if not request.user.is_superuser: 
        #     readonly.append('price_at_order')
        # УБРАЛ ЭТО УСЛОВИЕ

        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status == Order.STATUS_ISSUED:
            readonly.extend(['service', 'quantity', 'price_at_order'])
        return tuple(set(readonly))

    # has_add_permission и has_delete_permission без изменений
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