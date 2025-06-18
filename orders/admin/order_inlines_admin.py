# --- ПОРЦИЯ 1: ИМПОРТЫ И НАЧАЛО ФАЙЛА (60 строк) ---

from django import forms
from django.contrib import admin
from django.utils.html import format_html
from decimal import Decimal
from django.db.models import Sum, Q
from django.core.exceptions import ValidationError

from orders.forms import OrderProductItemForm
from ..models import OrderProductItem, OrderServiceItem, Order, Product, Service

# Вспомогательная функция
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

# НАШ ГЛАВНЫЙ "ПРОВЕРЯЮЩИЙ" КЛАСС - Он не даст сохранить заказ, если товара не хватает
class BaseOrderProductItemFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        
        # Собираем информацию о том, сколько какого товара заказываем
        product_quantities = {}
        for form in self.forms:
            # Пропускаем пустые или удаленные строки
            if not form.is_valid() or form.cleaned_data.get('DELETE'):
                continue
            
            product = form.cleaned_data.get('product')
            quantity = form.cleaned_data.get('quantity')

            if product and quantity:
                # Если один товар добавлен несколько раз, суммируем количество
                product_quantities[product.id] = product_quantities.get(product.id, 0) + quantity

        # Теперь для каждого товара проверяем, хватает ли его на складе
        for product_id, total_quantity_needed in product_quantities.items():
            try:
                product = Product.objects.get(pk=product_id)
                
                # Считаем, сколько товара на складе
                total_stock = product.stock_quantity or 0
                
                # Считаем, сколько зарезервировано в ДРУГИХ заказах
                reserved_query = OrderProductItem.objects.filter(
                    product=product
                ).exclude(
                    Q(order__status=Order.STATUS_ISSUED) | Q(order__status=Order.STATUS_CANCELLED)
                )
                # Если редактируем заказ, исключаем его старые резервы
                if self.instance and self.instance.pk:
                    reserved_query = reserved_query.exclude(order=self.instance)
                                # Считаем общий резерв в других заказах
                reserved_sum = reserved_query.aggregate(total_reserved=Sum('quantity'))
                total_reserved_in_other_orders = reserved_sum.get('total_reserved') or 0
                
                # Вычисляем, сколько товара реально доступно для заказа
                available_stock = total_stock - total_reserved_in_other_orders
                
                # ГЛАВНАЯ ПРОВЕРКА: если нужно больше, чем доступно - показываем ошибку
                if total_quantity_needed > available_stock:
                    raise ValidationError(
                        f"Недостаточно товара '{product.name}'. "
                        f"Доступно для заказа: {available_stock} шт., "
                        f"вы пытаетесь заказать: {total_quantity_needed} шт."
                    )
            except Product.DoesNotExist:
                raise ValidationError(f"Товар с ID {product_id} не найден.")


# Форма для товаров с меткой для JavaScript
class OrderProductItemAdminForm(forms.ModelForm):
    class Meta:
        model = OrderProductItem
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем CSS-класс к полю quantity для JavaScript
        if 'quantity' in self.fields:
            self.fields['quantity'].widget.attrs.update({'class': 'order-item-quantity'})
        
        instance = getattr(self, 'instance', None)
        if instance and instance.pk and instance.product and instance.price_at_order is not None:
            try:
                standard_price = instance.product.retail_price 
                if instance.price_at_order != standard_price:
                    self.fields['price_at_order'].widget.attrs['data-manual-price'] = 'true'
            except Product.DoesNotExist:
                pass
            except Exception as e:
                print(f"Error in OrderProductItemAdminForm __init__ for product {instance.product_id}: {e}")

# Начало основного класса таблицы товаров
class OrderProductItemInline(admin.TabularInline):
    model = OrderProductItem
    form = OrderProductItemAdminForm
    formset = BaseOrderProductItemFormSet  # <--- ПОДКЛЮЧАЕМ НАШ ПРОВЕРЯЮЩИЙ КЛАСС
    extra = 0 
    autocomplete_fields = ['product']
    
    fields = (
        'product', 
        'available_quantity',
        'cost_price_at_sale',
        'quantity', 
        'price_at_order',
        'display_item_total'
    )
    
    readonly_fields = (
        'available_quantity',
        'cost_price_at_sale',
        'display_item_total'
    )
    
    # Функция отображения "Доступно сейчас" с метками для JavaScript
    def available_quantity(self, obj):
        if not obj.product_id:
            return "—"

        product = obj.product
        total_stock = product.stock_quantity or 0
            # Считаем резерв во всех других заказах
        reserved_query = OrderProductItem.objects.filter(
            product=product
        ).exclude(
            Q(order__status=Order.STATUS_ISSUED) | Q(order__status=Order.STATUS_CANCELLED)
        )
        if obj.order_id:
            reserved_query = reserved_query.exclude(order_id=obj.order_id)
        
        reserved_sum = reserved_query.aggregate(total_reserved=Sum('quantity'))
        total_reserved_in_other_orders = reserved_sum.get('total_reserved') or 0
        
        # Считаем доступное количество для этой строки
        current_quantity = obj.quantity or 0
        initial_available = total_stock - total_reserved_in_other_orders - current_quantity

        # Формируем HTML с метками для JavaScript (чтобы цифры обновлялись автоматически)
        return format_html(
            '<span class="available-quantity-display" data-product-id="{}" data-stock-quantity="{}" data-reserved-externally="{}">{}</span>',
            product.id,
            total_stock,
            total_reserved_in_other_orders,
            initial_available
        )
    available_quantity.short_description = "Доступно сейчас"

    # Функция для подсчета суммы по строке
    def display_item_total(self, obj):
        if obj.pk and hasattr(obj, 'get_item_total') and obj.get_item_total() is not None: 
            return obj.get_item_total()
        elif obj.quantity is not None and obj.price_at_order is not None:
             try:
                return Decimal(obj.quantity) * Decimal(obj.price_at_order)
             except:
                return Decimal('0.00')
        return Decimal('0.00')
    display_item_total.short_description = "Сумма по строке"

    # Функция для блокировки полей в выданных/отмененных заказах
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status in (Order.STATUS_ISSUED, Order.STATUS_CANCELLED):
            readonly.extend(['product', 'quantity', 'price_at_order'])
        return tuple(set(readonly))

    # Запрет добавления товаров в выданные/отмененные заказы
    def has_add_permission(self, request, obj=None):
        parent_order = obj 
        if parent_order and parent_order.status in (Order.STATUS_ISSUED, Order.STATUS_CANCELLED): 
            return False
        return super().has_add_permission(request, obj)

    # Запрет удаления товаров из выданных/отмененных заказов
    def has_delete_permission(self, request, obj=None):
        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status in (Order.STATUS_ISSUED, Order.STATUS_CANCELLED): 
            return False
        return super().has_delete_permission(request, obj)


# --- БЛОК ДЛЯ УСЛУГ (остается без изменений) ---

# Форма для услуг
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
            except Service.DoesNotExist: 
                pass
            except Exception as e: 
                print(f"Error in OrderServiceItemAdminForm __init__ for service {instance.service_id}: {e}")

# Таблица услуг (без изменений)
class OrderServiceItemInline(admin.TabularInline):
    model = OrderServiceItem
    form = OrderServiceItemAdminForm
    extra = 0
    autocomplete_fields = ['service']
    fields = ('service', 'quantity', 'price_at_order', 'display_item_total')
    readonly_fields = ('display_item_total',)
        # Функция для подсчета суммы по строке услуг
    def display_item_total(self, obj):
        if obj.pk and hasattr(obj, 'get_item_total') and obj.get_item_total() is not None: 
            return obj.get_item_total()
        elif obj.quantity is not None and obj.price_at_order is not None:
            try: 
                return Decimal(obj.quantity) * Decimal(obj.price_at_order)
            except: 
                return Decimal('0.00')
        return Decimal('0.00')
    display_item_total.short_description = "Сумма по строке"
    
    # Функция для блокировки полей услуг в выданных/отмененных заказах
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status in (Order.STATUS_ISSUED, Order.STATUS_CANCELLED): 
            readonly.extend(['service', 'quantity', 'price_at_order'])
        return tuple(set(readonly))
    
    # Запрет добавления услуг в выданные/отмененные заказы
    def has_add_permission(self, request, obj=None):
        parent_order = obj
        if parent_order and parent_order.status in (Order.STATUS_ISSUED, Order.STATUS_CANCELLED): 
            return False
        return super().has_add_permission(request, obj)
    
    # Запрет удаления услуг из выданных/отмененных заказов
    def has_delete_permission(self, request, obj=None):
        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status in (Order.STATUS_ISSUED, Order.STATUS_CANCELLED): 
            return False
        return super().has_delete_permission(request, obj)

# --- КОНЕЦ ФАЙЛА ---