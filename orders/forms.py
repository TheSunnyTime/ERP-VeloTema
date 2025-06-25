# F:\CRM 2.0\ERP\orders\forms.py

from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import Order, OrderType, OrderProductItem
from dal import autocomplete

# --- ФОРМА для выбора товара в заказе ---
class OrderProductItemForm(forms.ModelForm):
    class Meta:
        model = OrderProductItem
        fields = '__all__'
        widgets = {
            'product': autocomplete.ModelSelect2(
                url='products:product-autocomplete',
                # --- ВОТ ОНА, ЭТА СТРОКА! ---
                # Этот атрибут говорит виджету, что он должен отображать HTML
                attrs={'data-html': True},
            ),
        }

# --- ФОРМАСЕТ для инлайнов товаров (оставь, если используешь) ---
class BaseOrderProductItemFormSet(forms.BaseInlineFormSet):
    pass

# --- ФОРМА ДЛЯ ЗАКАЗА (OrderAdminForm) ---
# Эту часть мы не трогаем, она отвечает за другую логику
class OrderAdminForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'performer' in self.fields:
            self.fields['performer'].required = False

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        order_type = cleaned_data.get('order_type')
        performer = cleaned_data.get('performer')
        payment_method_on_closure = cleaned_data.get('payment_method_on_closure')

        is_new_object = not self.instance or not self.instance.pk

        # Новый заказ не может быть сразу "Выдан"
        if is_new_object and status == Order.STATUS_ISSUED:
            self.add_error('status', ValidationError(
                "Новый заказ не может быть сразу создан со статусом 'Выдан'. "
                "Пожалуйста, выберите другой начальный статус."
            ))

        # Проверки для "Выдан"
        if status == Order.STATUS_ISSUED:
            if not payment_method_on_closure:
                self.add_error('payment_method_on_closure',
                                ValidationError("Метод оплаты должен быть указан, если статус заказа 'Выдан'.",
                                                code='payment_method_required_for_issue'))
            if order_type and order_type.name == OrderType.TYPE_REPAIR and not performer:
                self.add_error('performer',
                                ValidationError(f"Исполнитель должен быть указан для типа заказа '{OrderType.TYPE_REPAIR}' "
                                                f"при установке статуса 'Выдан'.",
                                                code='performer_required_for_repair_issue'))
        # Проверки для "Ремонт", если не "Новый" и не "Выдан"
        elif order_type and order_type.name == OrderType.TYPE_REPAIR and \
             status != Order.STATUS_NEW and not performer:
            self.add_error('performer',
                            ValidationError(f"Поле 'Исполнитель' обязательно для типа заказа '{OrderType.TYPE_REPAIR}', "
                                            f"если статус не '{dict(Order.STATUS_CHOICES).get(Order.STATUS_NEW)}'.",
                                            code='performer_required_for_repair_if_not_new_form'))
        return cleaned_data