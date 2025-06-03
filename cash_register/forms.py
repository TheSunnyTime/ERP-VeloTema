# F:\CRM 2.0\ERP\cash_register\forms.py
from django import forms
from .models import CashTransaction, CashRegister # Убедись, что CashRegister.TYPE_MAIN_ORGANIZATION доступен
from decimal import Decimal

# Имя группы для ограничения доступа к ГКО (должно совпадать с тем, что в admin.py)
# Если ты вынесешь это в какой-нибудь общий settings/constants файл, будет еще лучше.
GROUP_NO_GKO_ACCESS = "ИМЯ_ТВОЕЙ_ГРУППЫ_С_ОГРАНИЧЕННЫМ_ДОСТУПОМ_К_ГКО" 
# Например: GROUP_NO_GKO_ACCESS = "Операторы ТТ"


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
        min_value=Decimal('0.01')
    )
    destination_cash_register = forms.ModelChoiceField(
        queryset=CashRegister.objects.none(), # Начинаем с пустого queryset, заполним в __init__
        label="В кассу (получатель)",
        empty_label=None # Убираем пустой вариант, т.к. выбор обязателен
    )
    description = forms.CharField(
        label="Описание/Комментарий (необязательно)",
        widget=forms.Textarea,
        required=False
    )

    def __init__(self, *args, **kwargs):
        self.source_cash_register = kwargs.pop('source_cash_register', None)
        # Извлекаем request_user, переданный из CashRegisterAdmin
        self.request_user = kwargs.pop('request_user', None) 
        super().__init__(*args, **kwargs)

        if 'destination_cash_register' in self.fields:
            # Базовый queryset для касс назначения: активные и не являющиеся кассой-источником
            qs = CashRegister.objects.filter(is_active=True)
            if self.source_cash_register:
                qs = qs.exclude(pk=self.source_cash_register.pk)

            # Применяем дополнительную фильтрацию на основе прав пользователя, если он передан
            if self.request_user:
                user = self.request_user
                if not user.is_superuser:
                    user_groups = user.groups.all()
                    # Фильтр по allowed_groups
                    qs = qs.filter(allowed_groups__in=user_groups).distinct()

                    # Если пользователь в ограниченной группе, исключаем ГКО из выбора
                    # Это правило строгое: ограниченная группа не может выбирать ГКО как цель перевода.
                    if user_groups.filter(name=GROUP_NO_GKO_ACCESS).exists():
                        qs = qs.exclude(till_type=CashRegister.TYPE_MAIN_ORGANIZATION)
            
            self.fields['destination_cash_register'].queryset = qs

            # Если после всех фильтраций queryset пуст, то это может быть проблемой.
            # Можно добавить проверку и, например, отключить поле или выдать сообщение,
            # но стандартная ModelChoiceField просто покажет пустой список.


    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if self.source_cash_register and amount is not None: # Проверяем, что amount не None
            if self.source_cash_register.current_balance < amount:
                raise forms.ValidationError(
                    f"Недостаточно средств в кассе-источнике '{self.source_cash_register.name}'. "
                    f"Доступно: {self.source_cash_register.current_balance}, Запрошено: {amount}."
                )
        return amount

    def clean_destination_cash_register(self):
        destination = self.cleaned_data.get('destination_cash_register')
        if self.source_cash_register and destination: # Проверяем, что destination не None
            if self.source_cash_register.pk == destination.pk:
                raise forms.ValidationError("Касса-источник и касса-получатель не могут совпадать.")
            
            # Дополнительная серверная валидация: пользователь из ограниченной группы не должен выбрать ГКО
            # Эта проверка дублирует логику формирования queryset, но для надежности.
            if self.request_user and not self.request_user.is_superuser:
                if self.request_user.groups.filter(name=GROUP_NO_GKO_ACCESS).exists() and \
                   destination.till_type == CashRegister.TYPE_MAIN_ORGANIZATION:
                    raise forms.ValidationError(
                        f"Касса '{destination.name}' (ГКО) не может быть выбрана как касса назначения для вашей группы."
                    )
        return destination