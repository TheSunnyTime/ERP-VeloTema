# F:\CRM 2.0\erp\suppliers\forms.py
from django import forms
from .models import Supply # Импортируем модель Supply

class SupplyItemCSVImportForm(forms.Form):
    supply_to_update = forms.ModelChoiceField(
        queryset=Supply.objects.filter(status=Supply.STATUS_DRAFT).order_by('-receipt_date', '-id'),
        label="Выберите Поставку для импорта позиций",
        help_text="Будут показаны только поставки в статусе 'Черновик'.",
        empty_label=None # Убираем пустой вариант "---------", если нужно выбрать обязательно
    )
    csv_file = forms.FileField(
        label="CSV файл с позициями поставки",
        help_text="Выберите CSV файл. Колонки: ID Товара (или Артикул), Количество, Себестоимость за ед."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем поле supply_to_update более читаемым, если у Supply хороший __str__ метод
        self.fields['supply_to_update'].label_from_instance = lambda obj: f"№{obj.id} от {obj.receipt_date.strftime('%d.%m.%Y')} ({obj.supplier.name})"

        # Если поставок в статусе "Черновик" нет, можно добавить сообщение или задизейблить форму
        if not Supply.objects.filter(status=Supply.STATUS_DRAFT).exists():
            # Это можно обработать во view, чтобы не показывать форму вообще
            # или добавить placeholder, информирующий пользователя
            self.fields['supply_to_update'].queryset = Supply.objects.none()
            self.fields['supply_to_update'].help_text = "Нет доступных поставок в статусе 'Черновик' для импорта позиций."
            self.fields['supply_to_update'].empty_label = "Нет доступных поставок"
            # Можно даже задизейблить поля, если нет поставок
            # self.fields['supply_to_update'].disabled = True
            # self.fields['csv_file'].disabled = True


# Если понадобится более сложная форма для Supply (например, в админке),
# можно будет создать SupplyAdminForm(forms.ModelForm) здесь.