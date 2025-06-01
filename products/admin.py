# F:\CRM 2.0\ERP\products\admin.py
from django.contrib import admin, messages
from django.urls import path, reverse # <--- ДОБАВИЛ reverse
from django.shortcuts import render # render используется в reset_all_stock_view
from django.http import HttpResponseRedirect # используется в reset_all_stock_view
from django.core.exceptions import PermissionDenied # используется в reset_all_stock_view
from django.db import transaction # используется в reset_all_stock_view
from django.utils.html import format_html # Для ссылок в инлайнах

from .models import Category, Product
from suppliers.models import SupplyItem      # <--- ИМПОРТ SupplyItem
from orders.models import OrderProductItem, Order # <--- ИМПОРТ OrderProductItem и Order

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ('name',)

# --- ОПРЕДЕЛЯЕМ КЛАССЫ ИНЛАЙНОВ НА ВЕРХНЕМ УРОВНЕ ---

class SupplyItemInlineForProduct(admin.TabularInline):
    model = SupplyItem
    fk_name = 'product' 
    extra = 0
    can_delete = False 
    can_add = False    
    fields = ('display_supply_info', 'quantity_received', 'cost_price_per_unit')
    readonly_fields = ('display_supply_info', 'quantity_received', 'cost_price_per_unit')
    verbose_name = "История прихода"
    verbose_name_plural = "История приходов по этому товару"

    def display_supply_info(self, obj):
        if obj.supply:
            # Убедись, что у тебя есть URL с именем 'suppliers_supply_change' 
            # в админке для модели Supply приложения suppliers
            link = reverse("admin:suppliers_supply_change", args=[obj.supply.id])
            return format_html('<a href="{}">Поставка №{} от {} ({})</a>', 
                               link, obj.supply.id, obj.supply.supplier.name, obj.supply.receipt_date.strftime('%d.%m.%Y'))
        return "N/A"
    display_supply_info.short_description = "Информация о поставке"

    def has_change_permission(self, request, obj=None): 
        return False # Разрешаем только просмотр, не изменение

    # Добавляем has_view_permission, чтобы инлайн отображался
    def has_view_permission(self, request, obj=None):
        return True


class OrderProductItemInlineForProduct(admin.TabularInline):
    model = OrderProductItem
    fk_name = 'product'
    extra = 0
    can_delete = False
    can_add = False
    fields = ('display_order_info', 'quantity', 'price_at_order', 'cost_price_at_sale_display')
    readonly_fields = ('display_order_info', 'quantity', 'price_at_order', 'cost_price_at_sale_display')
    verbose_name = "История продажи/списания"
    verbose_name_plural = "История продаж/списаний этого товара"

    def display_order_info(self, obj):
        if obj.order:
            # Убедись, что у тебя есть URL с именем 'orders_order_change'
            link = reverse("admin:orders_order_change", args=[obj.order.id])
            status_display = obj.order.get_status_display()
            if obj.order.status == Order.STATUS_ISSUED: 
                return format_html('<a href="{}">Заказ №{} от {} ({})</a> - Статус: {}', 
                                   link, obj.order.id, obj.order.client.name if obj.order.client else "Клиент не указан", 
                                   obj.order.created_at.strftime('%d.%m.%Y'), status_display)
            return f"Заказ №{obj.order.id} (Статус: {status_display}) - не выдан"
        return "N/A"
    display_order_info.short_description = "Информация о заказе"

    def cost_price_at_sale_display(self,obj): 
        return obj.cost_price_at_sale
    cost_price_at_sale_display.short_description = "Себестоимость списания"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(order__status=Order.STATUS_ISSUED) 

    def has_change_permission(self, request, obj=None): 
        return False

    # Добавляем has_view_permission, чтобы инлайн отображался
    def has_view_permission(self, request, obj=None):
        return True

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'retail_price', 'cost_price', 'stock_quantity', 'updated_at')
    # Убедись, что 'is_active' есть в твоей модели Product, если ты его здесь используешь
    list_filter = ('category', 'is_active' if hasattr(Product, 'is_active') else 'category') 
    search_fields = ('name', 'sku')
    autocomplete_fields = ('category',)
    # Убедись, что 'created_at' и 'updated_at' есть в модели Product
    readonly_fields = (
        'created_at' if hasattr(Product, 'created_at') else None, 
        'updated_at' if hasattr(Product, 'updated_at') else None
    )
    # Убираем None из кортежа, если они там оказались
    readonly_fields = tuple(filter(None, readonly_fields))


    # Добавляем инлайны для истории
    inlines = [SupplyItemInlineForProduct, OrderProductItemInlineForProduct]

    # fieldsets можно будет настроить позже для лучшего вида, если нужно
    # fieldsets = (
    #     (None, {'fields': ('name', 'sku', 'category', 'is_active' if hasattr(Product, 'is_active') else None)}),
    #     ('Цены и остатки', {'fields': ('retail_price', 'cost_price', 'stock_quantity')}),
    #     ('Даты', {'fields': (('created_at', 'updated_at'),) if hasattr(Product, 'created_at') else ()})
    # )
    # fieldsets = tuple(fs for fs in fieldsets if fs[1]['fields'] and any(f for f in fs[1]['fields']))


    # Твой существующий get_urls и reset_all_stock_view
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'reset-all-stock/',
                self.admin_site.admin_view(self.reset_all_stock_view),
                name='products_product_reset_all_stock' # Имя для reverse должно быть products_product_reset_all_stock
            ),
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
            
            # Используем reverse для большей надежности URL
            return HttpResponseRedirect(reverse('admin:products_product_changelist'))

        context = {
            **self.admin_site.each_context(request),
            'title': 'Подтверждение: Обнулить все остатки товаров',
            'opts': self.model._meta,
            'action_name': 'reset_all_stock', # Это может быть не нужно, если ты не используешь в шаблоне
            'product_count': Product.objects.count(),
        }
        return render(
            request,
            'admin/products/product/reset_stock_confirmation.html',
            context
        )