# products/forms.py

from dal import autocomplete
from .models import Product
# Убедись, что импортируешь именно эти функции
from .search_utils import get_product_search_queryset, score_product, format_product_for_display
from django.db.models import QuerySet, Case, When
import logging
import json

logger = logging.getLogger(__name__)

class ProductAutocomplete(autocomplete.Select2QuerySetView):
    model = Product

    def get_queryset(self):
        qs = Product.objects.all()

        if not self.q:
            return qs.order_by('name')[:50]

        # ---!!! ИЗМЕНЕНИЕ НАЧАЛО !!!---
        # ШАГ 1: Находим всех возможных кандидатов
        candidate_products = get_product_search_queryset(qs, self.q, fields=['name', 'sku'])
        
        # ШАГ 2: Присваиваем им очки
        products_with_scores = []
        for product in candidate_products:
            score, score_details = score_product(product, self.q)
            if score > 0: # Добавляем только те, что имеют хоть какой-то положительный балл
                products_with_scores.append((score, product))
                # Логируем только значимые результаты
                logger.debug(json.dumps({
                    "event": "product_scored", "query": self.q, "product_id": product.pk,
                    "product_name": product.name, "score": score, "score_details": score_details
                }, ensure_ascii=False))

        # Сортируем по очкам
        products_with_scores.sort(key=lambda x: x[0], reverse=True)
        
        sorted_pks = [product.pk for score, product in products_with_scores]
        
        # ШАГ 3: Если найдено мало результатов, добавляем популярные товары
        # Это предотвращает пустую выдачу и всегда предлагает что-то пользователю
        MIN_RESULTS = 10
        if len(sorted_pks) < MIN_RESULTS:
            # Находим ID популярных товаров, которые ещё не в списке
            additional_pks = list(
                qs.exclude(pk__in=sorted_pks)
                  .order_by('-id')[:MIN_RESULTS - len(sorted_pks)]
                  .values_list('pk', flat=True)
            )
            sorted_pks.extend(additional_pks)

        if not sorted_pks:
            return Product.objects.none()

        # Сохраняем порядок
        preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(sorted_pks)])
        final_queryset = Product.objects.filter(pk__in=sorted_pks).order_by(preserved_order)
        
        logger.info(json.dumps({
            "event": "search_completed", "query": self.q, 
            "initial_candidates": candidate_products.count(),
            "final_results": final_queryset.count(),
            "top_result_id": sorted_pks[0] if sorted_pks else None
        }, ensure_ascii=False))

        return final_queryset
        # ---!!! ИЗМЕНЕНИЕ КОНЕЦ !!!---

    # Остальные методы класса (get_result_value, get_result_label и т.д.) без изменений
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