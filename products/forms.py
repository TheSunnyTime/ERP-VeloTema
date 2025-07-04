# products/forms.py (ФИНАЛЬНОЕ ВОССТАНОВЛЕНИЕ ПОИСКА И РЕГИСТРОНЕЗАВИСИМОСТЬ)

from dal import autocomplete
from .models import Product
from .search_utils import get_product_search_queryset, format_product_for_display
from django.db.models import QuerySet
from django.db.models import Q as DjangoQ # Используем alias, чтобы не конфликтовать с Q в search_utils

class ProductAutocomplete(autocomplete.Select2QuerySetView):
    """
    Автодополнение с надежной сортировкой в Python и регистронезависимым поиском.
    """
    model = Product # Обязательно указываем модель для DAL

    def get_queryset(self):
        # Получаем базовый QuerySet от родителя.
        # super().get_queryset() может применять свою фильтрацию.
        # Мы будем использовать свой, чтобы гарантировать регистронезависимость.
        # Поэтому НЕ вызываем super().get_queryset() здесь,
        # а начинаем с Product.objects.all()
        qs = Product.objects.all()

        if self.q:
            # Наш get_product_search_queryset уже использует iregex и .lower()
            candidate_products = get_product_search_queryset(qs, self.q, fields=['name', 'sku'])
            
            words = self.q.lower().split()

            def calculate_score(product):
                score = 0
                name_lower = product.name.lower()
                
                if product.get_available_stock_quantity > 0:
                    score += 10000 
                
                if name_lower.startswith(self.q.lower()):
                    score += 1000
                elif words and name_lower.startswith(words[0]):
                    score += 100

                if all(word in name_lower for word in words):
                    score += 50
                
                for word in words:
                    if word in name_lower:
                        score += 1
                
                return score

            # Конвертируем QuerySet в список для сортировки в Python.
            results_list = list(candidate_products)
            results_list.sort(key=calculate_score, reverse=True)
            
            # Возвращаем QuerySet из отсортированных PK.
            # Это должно сохранить порядок и быть регистронезависимым.
            return Product.objects.filter(pk__in=[p.pk for p in results_list])
        
        # Если нет поискового запроса, возвращаем QuerySet с базовой сортировкой
        return qs.order_by('name')[:50]
        
    def get_result_value(self, result):
        return str(result.pk)

    def get_result_label(self, result):
        return format_product_for_display(result)

    def get_selected_result_properties(self, result):
        return {
            'name': result.name,
            'sku': result.sku if result.sku else '',
            'retail_price': str(result.retail_price),
            'available_stock_quantity': result.get_available_stock_quantity,
        }