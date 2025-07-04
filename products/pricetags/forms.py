# products/pricetags/forms.py
from django import forms
from dal import autocomplete
from ..models import Product # Импортируем модель Product из родительского модуля products

class PricetagProductSearchForm(forms.Form):
    """
    Форма для поиска товаров с автодополнением Select2 для страницы печати ценников.
    """
    product = forms.ModelChoiceField(
        queryset=Product.objects.all(),
        widget=autocomplete.ModelSelect2(url='products:product-autocomplete'),
        label="Поиск товара для ценника",
        required=False, # Сделать необязательным, если пользователь может не выбрать ничего
    )