from django.db.models import Q

def get_product_search_queryset(queryset, search_term, fields=None):
    if not search_term:
        return queryset
    if fields is None:
        fields = ['name', 'sku']

    symbols = ['(', ')', ',', '.', '[', ']', '{', '}', ';', ':']
    for sym in symbols:
        search_term = search_term.replace(sym, ' ')

    words = [w for w in search_term.lower().split() if w]

    # --- Разница: теперь объединяем условия через ИЛИ, а не через И ---
    total_q = Q()
    for word in words:
        word_q = Q()
        for field in fields:
            word_q |= Q(**{f"{field}__icontains": word})
        total_q |= word_q  # <- вот здесь ИЛИ
    queryset = queryset.filter(total_q)
    return queryset