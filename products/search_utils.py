# F:\CRM 2.0\ERP\products\search_utils.py

from django.db.models import Q
from functools import reduce
import operator

# Эта функция теперь ТОЛЬКО ищет, но НЕ сортирует
def get_product_search_queryset(queryset, search_term, fields=None):
    """
    Находит всех кандидатов для поиска по "ИЛИ", НЕ СОРТИРУЕТ.
    """
    if fields is None:
        fields = ['name', 'sku']

    # Очистка и разбивка запроса
    symbols = ['(', ')', ',', '.', '[', ']', '{', '}', ';', ':']
    for sym in symbols:
        search_term = search_term.replace(sym, ' ')
    words = [w for w in search_term.lower().split() if w]

    if not words:
        return queryset.none()

    # Простой поиск по "ИЛИ", чтобы найти всех кандидатов
    conditions = [Q(**{f"{f}__iregex": w}) for w in words for f in fields]
    if not conditions:
        return queryset.none()
    
    query = reduce(operator.or_, conditions)
    return queryset.filter(query)


def format_product_for_display(item):
    """
    Показываем товар с информацией о количестве (без изменений).
    """
    quantity_available = item.get_available_stock_quantity
    
    if quantity_available > 0:
        status = f"Доступно: {int(quantity_available)}"
    else:
        status = "Недостат."
    
    sku_part = f" [{item.sku}]" if item.sku else ""
    return f"{item.name}{sku_part} - {status}"