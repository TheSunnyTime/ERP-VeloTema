from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils.html import format_html
from django.db.models import Q # <--- ИМПОРТ Q ДЛЯ КОМПЛЕКСНЫХ ЗАПРОСОВ

from .models import Category, Product
from suppliers.models import SupplyItem
from orders.models import OrderProductItem, Order

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    # Для категорий, если их немного, __icontains может быть достаточно,
    # но если тоже есть проблемы с регистром, можно применить аналогичный get_search_results
    search_fields = ('name__icontains',)

# ... (Твои инлайны SupplyItemInlineForProduct и OrderProductItemInlineForProduct остаются без изменений) ...
class SupplyItemInlineForProduct(admin.TabularInline): # Просто для полноты кода
    model = SupplyItem; fk_name = 'product'; extra = 0; can_delete = False; can_add = False
    fields = ('display_supply_info', 'quantity_received', 'cost_price_per_unit'); readonly_fields = fields
    verbose_name = "История прихода"; verbose_name_plural = "История приходов по этому товару"
    def display_supply_info(self, obj):
        if obj.supply:
            link = reverse("admin:suppliers_supply_change", args=[obj.supply.id])
            return format_html('<a href="{}">Поставка №{} от {} ({})</a>', link, obj.supply.id, obj.supply.supplier.name, obj.supply.receipt_date.strftime('%d.%m.%Y'))
        return "N/A"
    display_supply_info.short_description = "Информация о поставке"
    def has_change_permission(self, request, obj=None): return False
    def has_view_permission(self, request, obj=None): return True

class OrderProductItemInlineForProduct(admin.TabularInline): # Просто для полноты кода
    model = OrderProductItem; fk_name = 'product'; extra = 0; can_delete = False; can_add = False
    fields = ('display_order_info', 'quantity', 'price_at_order', 'cost_price_at_sale_display'); readonly_fields = fields
    verbose_name = "История продажи/списания"; verbose_name_plural = "История продаж/списаний этого товара"
    def display_order_info(self, obj):
        if obj.order:
            link = reverse("admin:orders_order_change", args=[obj.order.id])
            status_display = obj.order.get_status_display()
            if obj.order.status == Order.STATUS_ISSUED: return format_html('<a href="{}">Заказ №{} от {} ({})</a> - Статус: {}', link, obj.order.id, obj.order.client.name if obj.order.client else "Клиент не указан", obj.order.created_at.strftime('%d.%m.%Y'), status_display)
            return f"Заказ №{obj.order.id} (Статус: {status_display}) - не выдан"
        return "N/A"
    display_order_info.short_description = "Информация о заказе"
    def cost_price_at_sale_display(self,obj): return obj.cost_price_at_sale
    cost_price_at_sale_display.short_description = "Себестоимость списания"
    def get_queryset(self, request): return super().get_queryset(request).filter(order__status=Order.STATUS_ISSUED)
    def has_change_permission(self, request, obj=None): return False
    def has_view_permission(self, request, obj=None): return True


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'retail_price', 'cost_price', 'stock_quantity', 'updated_at')
    list_filter = ('category', 'is_active' if hasattr(Product, 'is_active') else 'category')
    
    # Оставляем базовые имена полей, так как логика поиска будет в get_search_results
    search_fields = ('name', 'sku') 
    
    autocomplete_fields = ('category',)
    # ... (readonly_fields и inlines как были) ...
    readonly_fields_list = []
    if hasattr(Product, 'created_at'): readonly_fields_list.append('created_at')
    if hasattr(Product, 'updated_at'): readonly_fields_list.append('updated_at')
    readonly_fields = tuple(readonly_fields_list)
    inlines = [SupplyItemInlineForProduct, OrderProductItemInlineForProduct]


    def get_search_results(self, request, queryset, search_term):
        # Вызываем родительский метод, чтобы получить базовый queryset и use_distinct
        # Он применит search_fields, но для SQLite с кириллицей это может быть регистрозависимо.
        queryset_standard, use_distinct_standard = super().get_search_results(request, queryset, search_term)

        # Теперь применяем наш кастомный регистронезависимый поиск, если search_term задан
        if search_term:
            # Создаем Q-объекты для регистронезависимого поиска по нужным полям
            # Используем __iregex, так как он показал себя лучше для кириллицы в SQLite
            # в нашем предыдущем обсуждении.
            
            # Поля, по которым мы хотим искать регистронезависимо
            custom_search_fields = ['name', 'sku'] # Поля из self.search_fields, для которых нужен __iregex

            q_objects = Q() # Пустой Q-объект для | (OR) оператора
            for field_name in custom_search_fields:
                # Убедимся, что поле текстовое или может быть приведено к тексту для iregex
                # Для SKU это может быть важно, если он числовой, тогда iregex не подойдет.
                # Если SKU числовой, его нужно искать отдельно или преобразовывать в строку.
                # Для примера, предполагаем, что name и sku - текстовые.
                q_objects |= Q(**{f"{field_name}__iregex": search_term})
            
            # Фильтруем исходный queryset (до применения стандартного поиска)
            # или можно фильтровать queryset_standard, если хотим сузить уже найденное.
            # Лучше фильтровать исходный queryset, чтобы наш поиск был главным.
            queryset_custom = self.model.objects.filter(q_objects)
            
            # Объединяем результаты или просто используем наш кастомный результат
            # Если мы хотим полностью заменить стандартный поиск нашим, то:
            queryset = queryset_custom
            use_distinct = True # iregex может потребовать distinct
            
            # Если мы хотим ДОПОЛНИТЬ стандартный поиск (может дать больше результатов, но и дубликаты):
            # queryset = (queryset_standard | queryset_custom).distinct()
            # use_distinct = False # .distinct() уже применен

        else: # Если search_term пустой, просто возвращаем стандартный queryset
            queryset = queryset_standard
            use_distinct = use_distinct_standard
            
        return queryset, use_distinct

    # (Твои get_urls и reset_all_stock_view остаются без изменений)
    # ... (get_urls, reset_all_stock_view) ...
    def get_urls(self): # Просто для полноты кода
        urls = super().get_urls(); custom_urls = [path('reset-all-stock/', self.admin_site.admin_view(self.reset_all_stock_view), name='products_product_reset_all_stock')]; return custom_urls + urls
    def reset_all_stock_view(self, request): # Просто для полноты кода
        if not request.user.is_superuser: raise PermissionDenied("У вас нет прав для выполнения этой операции.")
        if request.method == 'POST':
            try:
                with transaction.atomic(): updated_count = Product.objects.all().update(stock_quantity=0)
                self.message_user(request, f"Остатки для {updated_count} товаров были успешно обнулены.", messages.SUCCESS)
            except Exception as e: self.message_user(request, f"Произошла ошибка при обнулении остатков: {e}", messages.ERROR)
            return HttpResponseRedirect(reverse('admin:products_product_changelist'))
        context = {**self.admin_site.each_context(request), 'title': 'Подтверждение: Обнулить все остатки товаров', 'opts': self.model._meta, 'product_count': Product.objects.count()}; return render(request, 'admin/products/product/reset_stock_confirmation.html', context)