# F:\CRM 2.0\ERP\products\search_utils.py

from django.db.models import Q
from functools import reduce
import operator
import re
from unidecode import unidecode

# ===================================================================
# СЛОВАРИ ДАННЫХ (КЛЮЧ К УСПЕХУ)
# ===================================================================

# Пополняй этот список, чтобы поиск лучше распознавал бренды
KNOWN_BRANDS = [
    'cst', 'chaoyang', 'maxxis', 'schwalbe', 'mitas', 'rubena', 'gekon', 'kenda',
    'shimano', 'continental', 'format', 'west biking', 'force', 'polisport'
]

# Пополняй этот список синонимами и частыми опечатками
SYNONYM_MAP = {
    'велопокрышка': 'покрышка',
    'велосипедная покрышка': 'покрышка',
    'покрыха': 'покрышка',
    'калеса': 'колесо',
    'вила': 'вилка',
}

# ===================================================================
# ФУНКЦИИ ПОИСКА И РАНЖИРОВАНИЯ
# ===================================================================

def get_product_search_queryset(queryset, search_term, fields=None):
    """
    ЭТАП 1: Мягкий поиск кандидатов по "ИЛИ". Находит всё, где есть хотя бы одно слово.
    """
    if fields is None:
        fields = ['name', 'sku']
    
    # ---!!! ВАЖНОЕ ИЗМЕНЕНИЕ !!!---
    # Используем более надёжный способ разделения слов.
    # Он корректно отделит "20" от "20x1.95" и "cst" от "покрышкаCST".
    words = [w for w in re.split(r'[\s,./\(\)\[\]\{\}\-:"х]+', search_term.lower()) if w]

    if not words:
        return queryset.none()

    # Ищем по "ИЛИ", чтобы собрать всех возможных кандидатов
    conditions = [Q(**{f"{field}__icontains": word}) for word in words for field in fields]
    query = reduce(operator.or_, conditions)
    return queryset.filter(query).distinct()


def score_product(product, query):
    """
    ЭТАП 2: Умное ранжирование. Чем больше совпадений - тем выше балл.
    """
    # 1. Нормализация текста для точного и честного сравнения
    # unidecode решает проблему с русскими и английскими буквами ('с' и 'c')
    clean_query = unidecode(query.lower())
    clean_name = unidecode(product.name.lower())

    for s, replacement in SYNONYM_MAP.items():
        clean_query = clean_query.replace(unidecode(s), unidecode(replacement))
        clean_name = clean_name.replace(unidecode(s), unidecode(replacement))
    
    # ---!!! ГЛАВНОЕ ИЗМЕНЕНИЕ: ПРАВИЛЬНЫЙ РАЗБОР НА СЛОВА !!!---
    # Эта регулярка находит все последовательности букв и цифр как отдельные слова
    query_words = set(re.findall(r'\b\w+\b', clean_query))
    name_words = set(re.findall(r'\b\w+\b', clean_name))

    score = 0
    score_details = {}

    # 2. Главный бонус: считаем, сколько слов из запроса совпало с названием
    matched_words = query_words.intersection(name_words)
    
    # Даём ОЧЕНЬ большой бонус за каждое совпавшее слово.
    # Товар с 3-мя совпадениями всегда будет выше товара с 2-мя.
    if len(matched_words) > 0:
        score += len(matched_words) * 5000
        score_details['matched_words_count'] = len(matched_words)
        score_details['matched_words_score'] = len(matched_words) * 5000

    # 3. Дополнительный бонус за бренд
    for brand in KNOWN_BRANDS:
        if brand in query_words and brand in name_words:
            score += 3000
            score_details[f'brand_match_{brand}'] = 3000
    
    # 4. Небольшой бонус за точное совпадение всей фразы
    if clean_query in clean_name:
        score += 100
        score_details['full_phrase_match'] = 100

    # 5. Приоритет наличия
    if product.get_available_stock_quantity > 0:
        score += 1000
        score_details['stock_bonus'] = 1000
            
    return score, score_details


def format_product_for_display(item):
    """Отображение товара (без изменений)."""
    quantity_available = item.get_available_stock_quantity
    status = f"Доступно: {int(quantity_available)}" if quantity_available > 0 else "Недостат."
    sku_part = f" [{item.sku}]" if item.sku else ""
    return f"{item.name}{sku_part} - {status}"