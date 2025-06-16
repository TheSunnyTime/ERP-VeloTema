from dal import autocomplete
from .models import Product
from .search_utils import get_product_search_queryset  # <-- Добавь этот импорт

class ProductAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Product.objects.all()
        if self.q:
            # Используем твою функцию для поиска по названию и артикулу
            qs = get_product_search_queryset(qs, self.q, fields=['name', 'sku'])
        return qs