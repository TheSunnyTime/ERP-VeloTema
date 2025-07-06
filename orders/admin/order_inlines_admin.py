# --- ПОРЦИЯ 1: ИМПОРТЫ И НАЧАЛО ФАЙЛА (60 строк) ---

from django import forms
from django.contrib import admin
from django.utils.html import format_html
from decimal import Decimal
from django.db.models import Sum, Q
from django.core.exceptions import ValidationError
from dal import autocomplete  # <--- ВОТ ОН, НЕДОСТАЮЩИЙ ИМПОРТ

from orders.forms import OrderProductItemForm
from .service_admin_forms import OrderServiceItemAdminForm # <-- ИЗМЕНЕНИЕ: Импортируем из нового файла
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
                
                # ✅ ИСПРАВЛЕНИЕ: Правильно получаем доступный остаток
                available_stock = product.get_available_stock_quantity  # БЕЗ СКОБОК

                # Если редактируем заказ, учитываем что товар уже в этом заказе
                if self.instance and self.instance.pk:
                    # Проверяем сколько этого товара уже в текущем заказе
                    current_order_quantity = OrderProductItem.objects.filter(
                        order=self.instance,
                        product=product
                    ).aggregate(total_in_order=Sum('quantity'))
                    current_in_order = current_order_quantity.get('total_in_order') or 0
                    
                    # Добавляем это количество к доступному (так как оно не должно блокировать)
                    available_stock += current_in_order
                
                # ГЛАВНАЯ ПРОВЕРКА: если нужно больше, чем доступно - показываем ошибку
                if total_quantity_needed > available_stock:
                    raise ValidationError(
                        f"Недостаточно товара '{product.name}'. "
                        f"Доступно для заказа: {available_stock} шт., "
                        f"вы пытаетесь заказать: {total_quantity_needed} шт."
                    )
            except Product.DoesNotExist:
                raise ValidationError(f"Товар с ID {product_id} не найден.")

# Начало основного класса таблицы товаров
class OrderProductItemInline(admin.TabularInline):
    model = OrderProductItem
    form = OrderProductItemForm
    formset = BaseOrderProductItemFormSet
    extra = 0
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            kwargs["widget"] = autocomplete.ModelSelect2(
                url='products:product-autocomplete'
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    fields = ('product', 'available_quantity', 'cost_price_at_sale', 'quantity', 'price_at_order', 'display_item_total')
    readonly_fields = ('available_quantity', 'cost_price_at_sale', 'display_item_total')
    
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
    
    # ✅ ИСПРАВЛЕНИЕ 2: Функция отображения "Доступно сейчас" с правильным расчетом
    def available_quantity(self, obj):
        """Показывает сколько товара доступно для заказа прямо сейчас"""
        # Если товар не выбран - показываем прочерк
        if not obj.product_id:
            return "—"

        try:
            product = obj.product
            
            # Получаем ПРАВИЛЬНО доступный остаток (уже с учетом резерва!)
            available_stock = product.get_available_stock_quantity
            
            # Общий остаток и резерв - для JavaScript
            total_stock = product.get_real_stock_quantity
            reserved_externally = total_stock - available_stock
            
            # Текущее количество в этом заказе
            current_quantity = obj.quantity or 0
            
            # Если это существующий заказ, добавляем текущее количество к доступному
            if obj.pk and obj.order_id:
                # Для существующего товара показываем: доступный + уже заказанный
                display_available = available_stock + current_quantity
            else:
                # Для нового товара показываем просто доступный
                display_available = available_stock
            
            # Возвращаем HTML с ПРАВИЛЬНЫМИ данными для JavaScript
            return format_html(
                '<span class="available-quantity-display" '
                'data-product-id="{}" '
                'data-stock-quantity="{}" '
                'data-reserved-externally="{}">'
                '{}'
                '</span>',
                product.id,
                total_stock,        # Общий остаток
                reserved_externally, # Правильный резерв
                display_available   # Доступно сейчас
            )
            
        except Exception as e:
            # Если что-то пошло не так - показываем ошибку
            return format_html('<span style="color: red;">Ошибка: {}</span>', str(e))
            # Настройки для колонки "Остаток"
    available_quantity.short_description = "Остаток"
    available_quantity.help_text = "Сколько товара можно заказать сейчас. Считается: общий остаток минус резерв в других заказах"


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

# Таблица услуг (без изменений)
class OrderServiceItemInline(admin.TabularInline):
    model = OrderServiceItem
    form = OrderServiceItemAdminForm # Используем нашу кастомную форму
    extra = 0
    
    # Указываем Django использовать наш новый виджет автодополнения
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "service":
            kwargs["widget"] = autocomplete.ModelSelect2(
                url='orders:service-autocomplete'  # Ссылка на наш новый URL
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    fields = ('service', 'quantity', 'price_at_order', 'display_item_total')
    readonly_fields = ('display_item_total',)

    def display_item_total(self, obj):
        return obj.get_item_total()
    display_item_total.short_description = "Сумма"
    
    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status in (Order.STATUS_ISSUED, Order.STATUS_CANCELLED):
            readonly.extend(['service', 'quantity', 'price_at_order'])
        return tuple(set(readonly))
    
    def has_add_permission(self, request, obj=None):
        parent_order = obj
        if parent_order and parent_order.status in (Order.STATUS_ISSUED, Order.STATUS_CANCELLED):
            return False
        return super().has_add_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        parent_order = get_parent_order_from_request(request, obj)
        if parent_order and parent_order.status in (Order.STATUS_ISSUED, Order.STATUS_CANCELLED):
            return False
        return super().has_delete_permission(request, obj)
