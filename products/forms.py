# products/forms.py (ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ СОРТИРОВКИ ПО НАЛИЧИЮ)

from dal import autocomplete
from .models import Product
from .search_utils import get_product_search_queryset, format_product_for_display
from django.db.models import QuerySet, Case, When # <--- ДОБАВЛЕНО: Case, When

class ProductAutocomplete(autocomplete.Select2QuerySetView):
    """
    Автодополнение с надежной сортировкой в Python и регистронезависимым поиском.
    """
    model = Product 

    def get_queryset(self):
        qs = Product.objects.all()

        if self.q:
            candidate_products = get_product_search_queryset(qs, self.q, fields=['name', 'sku'])
            
            words = self.q.lower().split()

            # МЫ БУДЕМ СОРТИРОВАТЬ ТУТ, А ПОТОМ СОХРАНЯТЬ ПОРЯДОК
            products_with_scores = []
            for product in list(candidate_products): # <--- Обязательно конвертируем в список
                score = 0
                name_lower = product.name.lower()
                
                if product.get_available_stock_quantity > 0:
                    score += 10000 
                else:
                    score -= 10000 # Штраф за отсутствие в наличии
                
                if name_lower.startswith(self.q.lower()):
                    score += 1000
                elif words and name_lower.startswith(words[0]):
                    score += 100

                if all(word in name_lower for word in words):
                    score += 50
                
                for word in words:
                    if word in name_lower:
                        score += 1
                
                products_with_scores.append((score, product)) # Сохраняем счет и продукт

            # Сортируем список по счету (от большего к меньшему)
            products_with_scores.sort(key=lambda x: x[0], reverse=True)
            
            # Получаем отсортированные PK в правильном порядке
            sorted_pks = [product.pk for score, product in products_with_scores]
            
            # Создаем QuerySet, который сохраняет этот порядок.
            # Это делается с помощью Case и When.
            # Если sorted_pks пуст, возвращаем пустой QuerySet.
            if not sorted_pks:
                return Product.objects.none()

            # Создаем список When условий для каждого PK
            preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(sorted_pks)])
            
            # Фильтруем по PK и сортируем по сохраненному порядку
            return Product.objects.filter(pk__in=sorted_pks).order_by(preserved_order)
        
        # Если нет поискового запроса, возвращаем QuerySet с базовой сортировкой (как раньше)
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