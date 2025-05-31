# F:\CRM 2.0\ERP\cash_register\forms.py
from django import forms
from .models import CashTransaction, CashRegister
from decimal import Decimal # <--- ИСПРАВЛЕННЫЙ ИМПОРТ

class CashTransactionAdminForm(forms.ModelForm):
    class Meta:
        model = CashTransaction
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        transaction_type = cleaned_data.get("transaction_type")
        expense_category = cleaned_data.get("expense_category")
        order = cleaned_data.get("order")

        if transaction_type == CashTransaction.TRANSACTION_TYPE_EXPENSE:
            if not expense_category:
                self.add_error('expense_category', 
                               "Статья расхода обязательна для типа операции 'Расход'.")
            if order:
                self.add_error('order',
                               "Расходные операции не должны быть привязаны к Заказу (он используется для прихода от продаж).")

        elif transaction_type == CashTransaction.TRANSACTION_TYPE_INCOME:
            if expense_category:
                cleaned_data['expense_category'] = None

        return cleaned_data

class TransferFundsForm(forms.Form):
    amount = forms.DecimalField(
        label="Сумма перемещения", 
        max_digits=12, 
        decimal_places=2,
        min_value=Decimal('0.01') # Теперь Decimal здесь будет известен
    )
    destination_cash_register = forms.ModelChoiceField(
        queryset=CashRegister.objects.filter(is_active=True),
        label="В кассу (получатель)",
        empty_label=None
    )
    description = forms.CharField(
        label="Описание/Комментарий (необязательно)", 
        widget=forms.Textarea, 
        required=False
    )

    def __init__(self, *args, **kwargs):
        self.source_cash_register = kwargs.pop('source_cash_register', None)
        super().__init__(*args, **kwargs)

        if self.source_cash_register and 'destination_cash_register' in self.fields:
            self.fields['destination_cash_register'].queryset = \
                CashRegister.objects.filter(is_active=True).exclude(pk=self.source_cash_register.pk)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if self.source_cash_register and amount: # amount может быть None, если поле не заполнено и required=False
            if self.source_cash_register.current_balance < amount:
                raise forms.ValidationError(
                    f"Недостаточно средств в кассе-источнике '{self.source_cash_register.name}'. "
                    f"Доступно: {self.source_cash_register.current_balance}, Запрошено: {amount}."
                )
        return amount

    def clean_destination_cash_register(self):
        destination = self.cleaned_data.get('destination_cash_register')
        if self.source_cash_register and destination and self.source_cash_register.id == destination.id:
            raise forms.ValidationError("Касса-источник и касса-получатель не могут совпадать.")
        return destination