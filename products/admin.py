# F:\CRM 2.0\ERP\products\admin.py
from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.core.exceptions import PermissionDenied
from django.db import transaction
from .models import Category, Product

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # ----- ИЗМЕНЕНИЯ ЗДЕСЬ -----
    list_display = ('name', 'sku', 'category', 'retail_price', 'cost_price', 'stock_quantity') # Заменили на cost_price
    # ... остальной код ...
    list_filter = ('category',) # Убрали 'is_active'
    # ----- КОНЕЦ ИЗМЕНЕНИЙ -----
    search_fields = ('name', 'sku')
    autocomplete_fields = ('category',)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'reset-all-stock/',
                self.admin_site.admin_view(self.reset_all_stock_view),
                name='products_product_reset_all_stock'
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

            return HttpResponseRedirect("../")

        context = {
            **self.admin_site.each_context(request),
            'title': 'Подтверждение: Обнулить все остатки товаров',
            'opts': self.model._meta,
            'action_name': 'reset_all_stock',
            'product_count': Product.objects.count(),
        }
        return render(
            request,
            'admin/products/product/reset_stock_confirmation.html',
            context
        )