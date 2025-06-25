# F:\CRM 2.0\ERP\products\forms.py

from dal import autocomplete
from .models import Product
# Нам больше не нужен format_html, так как JS делает всю работу
from .search_utils import get_product_search_queryset, format_product_for_display

class ProductAutocomplete(autocomplete.Select2QuerySetView):
    """
    Автодополнение с надежной сортировкой в Python.
    Логика окрашивания полностью в product_highlight.js.
    """
    
    # Этот метод мы не трогаем. Он работает идеально.
    def get_queryset(self):
        qs = Product.objects.all()

        if self.q:
            search_results = get_product_search_queryset(qs, self.q, fields=['name', 'sku'])
            
            words = self.q.lower().split()

            def calculate_score(product):
                score = 0
                name_lower = product.name.lower()
                
                if product.get_available_stock_quantity > 0:
                    score += 10000
                
                if name_lower.startswith(self.q.lower()):
                    score += 1000
                elif name_lower.startswith(words[0]):
                    score += 100

                if all(word in name_lower for word in words):
                    score += 50
                
                for word in words:
                    if word in name_lower:
                        score += 1
                
                return score

            results_list = list(search_results)
            results_list.sort(key=calculate_score, reverse=True)
            
            return results_list
        
        return qs.order_by('name')[:50]
        
    def get_result_label(self, item):
        """
        Просто возвращаем текст. Всю работу по окрашиванию делает JS.
        """
        return format_product_for_display(item)