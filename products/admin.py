# products/admin.py
from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils.html import format_html
from django.db.models import Q

from .models import Category, Product
from suppliers.models import SupplyItem, Supply
from orders.models import OrderProductItem, Order # Order уже импортирован
# Импортируем OrderStatusColor
from uiconfig.models import SupplyStatusColor, OrderStatusColor # <--- ДОБАВЛЕН OrderStatusColor
from .search_utils import get_product_search_queryset

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ('name__icontains',)

class SupplyItemInlineForProduct(admin.TabularInline):
    model = SupplyItem
    fk_name = 'product'
    extra = 0
    can_delete = False
    verbose_name = "История прихода"
    verbose_name_plural = "История приходов по этому товару"

    _supply_status_colors_map = None

    @classmethod
    def _initialize_status_colors(cls): # Переименуем для ясности, что это для Supply
        if cls._supply_status_colors_map is None:
            try:
                cls._supply_status_colors_map = {
                    color.status_key: color.hex_color
                    for color in SupplyStatusColor.objects.all()
                }
            except Exception as e:
                print(f"Warning: Could not load supply status colors in SupplyItemInlineForProduct: {e}")
                cls._supply_status_colors_map = {}
    
    def __init__(self, parent_model, admin_site):
        super().__init__(parent_model, admin_site)
        self.__class__._initialize_status_colors() 

    def display_supply_info(self, obj: SupplyItem):
        if obj.supply:
            link = reverse("admin:suppliers_supply_change", args=[obj.supply.id])
            return format_html('<a href="{}">Поставка №{} от {} ({})</a>', 
                               link, 
                               obj.supply.id, 
                               obj.supply.supplier.name, 
                               obj.supply.receipt_date.strftime('%d.%m.%Y'))
        return "N/A"
    display_supply_info.short_description = "Поставка"

    def display_supply_status(self, obj: SupplyItem):
        if not obj.supply:
            return "N/A"
        
        status_key = obj.supply.status
        status_display = obj.supply.get_status_display()
        
        if self._supply_status_colors_map:
            hex_color = self._supply_status_colors_map.get(status_key)
            if hex_color:
                try:
                    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
                    text_color = '#ffffff' if (r * 0.299 + g * 0.587 + b * 0.114) < 128 else '#000000'
                    return format_html(
                        '<span style="background-color: {0}; padding: 2px 5px; border-radius: 3px; color: {1};"><strong>{2}</strong></span>',
                        hex_color,
                        text_color,
                        status_display
                    )
                except ValueError:
                    pass 
        return status_display
    display_supply_status.short_description = "Статус поставки"

    fields = ('display_supply_info', 'display_supply_status', 'quantity_received', 'cost_price_per_unit', 'quantity_remaining_in_batch')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


class OrderProductItemInlineForProduct(admin.TabularInline):
    model = OrderProductItem
    autocomplete_fields = ['product']  # Эта строка включает автодополнение товаров
    fk_name = 'product'
    extra = 0
    can_delete = False
    verbose_name = "История продажи/списания"
    verbose_name_plural = "История продаж/списаний этого товара"

    _order_status_colors_map = None

    @classmethod
    def _initialize_order_status_colors(cls):
        if cls._order_status_colors_map is None:
            try:
                cls._order_status_colors_map = {
                    color.status_key: color.hex_color
                    for color in OrderStatusColor.objects.all()
                }
            except Exception as e:
                print(f"Warning: Could not load order status colors in OrderProductItemInlineForProduct: {e}")
                cls._order_status_colors_map = {}
    
    def __init__(self, parent_model, admin_site):
        super().__init__(parent_model, admin_site)
        self.__class__._initialize_order_status_colors() 

    # --- Изменения здесь ---
    def display_order_number_link(self, obj: OrderProductItem):
        if obj.order:
            link = reverse("admin:orders_order_change", args=[obj.order.id])
            # Попробуем вернуть только номер заказа как ссылку
            return format_html('<a href="{}">Заказ №{}</a>', link, obj.order.id)
        return "N/A"
    display_order_number_link.short_description = "Заказ №" # Короткое название для колонки

    def display_order_client_and_date(self, obj: OrderProductItem): # Отдельное поле для клиента и даты
        if obj.order:
            client_name = obj.order.client.get_full_name_or_company() if obj.order.client else "Клиент не указан"
            return f"{client_name} ({obj.order.created_at.strftime('%d.%m.%Y')})"
        return "N/A"
    display_order_client_and_date.short_description = "Клиент (Дата)"
    # --- Конец изменений ---

    def colored_order_status(self, obj: OrderProductItem):
        if not obj.order:
            return "N/A"
        
        status_key = obj.order.status
        status_display = obj.order.get_status_display()
        
        if self._order_status_colors_map:
            hex_color = self._order_status_colors_map.get(status_key)
            if hex_color:
                try:
                    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
                    text_color = '#ffffff' if (r * 0.299 + g * 0.587 + b * 0.114) < 128 else '#000000'
                    return format_html(
                        '<span style="background-color: {0}; padding: 2px 5px; border-radius: 3px; color: {1};"><strong>{2}</strong></span>',
                        hex_color,
                        text_color,
                        status_display
                    )
                except ValueError:
                    pass 
        return status_display
    colored_order_status.short_description = "Статус заказа"

    def item_cost_price_at_sale(self, obj: OrderProductItem):
        return obj.cost_price_at_sale
    item_cost_price_at_sale.short_description = "Себестоимость списания"
    
    # Обновляем fields и readonly_fields
    list_display_fields = (
        'display_order_number_link',      # Ссылка на номер заказа
        'colored_order_status',
        'quantity', 
        'price_at_order', 
        'item_cost_price_at_sale'
    )
    
    fields = list_display_fields 
    readonly_fields = list_display_fields

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('order', 'order__client').filter(order__status=Order.STATUS_ISSUED) # Добавил select_related

    def has_add_permission(self, request, obj=None): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False



@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'retail_price', 'cost_price', 'stock_quantity', 'updated_at')
    list_filter = ('category', 'is_active' if hasattr(Product, 'is_active') else 'category')
    search_fields = ('name', 'sku') 
    autocomplete_fields = ('category',)

    # readonly_fields формируем универсально
    readonly_fields_list = ['stock_quantity', 'cost_price']
    if hasattr(Product, 'created_at'): 
        readonly_fields_list.append('created_at')
    if hasattr(Product, 'updated_at'): 
        readonly_fields_list.append('updated_at')
    readonly_fields = tuple(set(readonly_fields_list))

    inlines = [SupplyItemInlineForProduct, OrderProductItemInlineForProduct]

    def get_search_results(self, request, queryset, search_term):
        # Только наш расширенный поиск, без стандартного Django
        if search_term:
            queryset = get_product_search_queryset(queryset, search_term, fields=['name', 'sku'])
            use_distinct = False
        else:
            use_distinct = False
        return queryset, use_distinct

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'reset-all-stock/', 
                self.admin_site.admin_view(self.reset_all_stock_view), 
                name='products_product_reset_all_stock'
            )
        ]
        return custom_urls + urls

    def reset_all_stock_view(self, request):
        if not request.user.is_superuser: 
            raise PermissionDenied("У вас нет прав для выполнения этой операции.")
        
        if request.method == 'POST':
            try:
                with transaction.atomic(): 
                    updated_count = Product.objects.all().update(stock_quantity=0)
                self.message_user(request, f"Остатки для {updated_count} товаров были успешно обнулены.", messages.SUCCESS)
            except Exception as e: 
                self.message_user(request, f"Произошла ошибка при обнулении остатков: {e}", messages.ERROR)
            return HttpResponseRedirect(reverse('admin:products_product_changelist'))
        
        context = {
            **self.admin_site.each_context(request), 
            'title': 'Подтверждение: Обнулить все остатки товаров', 
            'opts': self.model._meta, 
            'product_count': Product.objects.count()
        }
        return render(request, 'admin/products/product/reset_stock_confirmation.html', context)