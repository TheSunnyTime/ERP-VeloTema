# F:\CRM 2.0\ERP\cash_register\models.py
from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.models import Group

# Модель ExpenseCategory (Статья расхода)
class ExpenseCategory(models.Model):
    # --- НАЧАЛО ИЗМЕНЕНИЙ ---
    CATEGORY_MANDATORY = 'mandatory'
    CATEGORY_OPTIONAL = 'optional'
    EXPENSE_TYPE_CATEGORY_CHOICES = [
        (CATEGORY_MANDATORY, 'Обязательные'),
        (CATEGORY_OPTIONAL, 'Необязательные'),
    ]
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    name = models.CharField(max_length=150, unique=True, verbose_name="Название статьи расхода")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    
    # --- НАЧАЛО ИЗМЕНЕНИЙ ---
    expense_type_category = models.CharField(
        max_length=20,
        choices=EXPENSE_TYPE_CATEGORY_CHOICES,
        default=CATEGORY_OPTIONAL, # По умолчанию - необязательные, или выберите другое
        verbose_name="Категория статьи расхода"
    )
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---
    
    is_default_for_supply_payment = models.BooleanField(
        default=False,
        verbose_name="Статья по умолчанию для оплаты поставок",
        help_text="Отметьте, если эта статья должна автоматически использоваться при оплате поставок."
    )

    class Meta:
        verbose_name = "Статья расхода"
        verbose_name_plural = "Статьи расходов"
        ordering = ['name']

    def __str__(self):
        return self.name

# Модель CashRegister (Касса) - БЕЗ ИЗМЕНЕНИЙ
class CashRegister(models.Model):
    TYPE_RETAIL_POINT = 'retail_point'
    TYPE_MAIN_ORGANIZATION = 'main_organization'
    TILL_TYPE_CHOICES = [
        (TYPE_RETAIL_POINT, 'Касса торговой точки'),
        (TYPE_MAIN_ORGANIZATION, 'Главная касса организации'),
    ]

    name = models.CharField(max_length=100, unique=True, verbose_name="Название кассы")
    till_type = models.CharField(max_length=20, choices=TILL_TYPE_CHOICES, default=TYPE_RETAIL_POINT, verbose_name="Тип кассы")
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name="Текущий баланс")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    description = models.TextField(blank=True, null=True, verbose_name="Описание кассы")
    
    is_default_for_cash = models.BooleanField(default=False, verbose_name="Касса по умолчанию для наличных (из заказов)")
    is_default_for_card = models.BooleanField(default=False, verbose_name="Касса по умолчанию для карт (из заказов)")
    
    is_gko_for_supply_payment = models.BooleanField(
        default=False,
        verbose_name="ГКО для оплаты поставок",
        help_text="Отметьте, если это ГКО, из которой могут оплачиваться поставки."
    )
    
    allowed_groups = models.ManyToManyField(
        Group, 
        blank=True, 
        verbose_name="Группы с доступом к этой кассе", 
        help_text="Если группы не выбраны, доступ к кассе может быть ограничен."
    )

    class Meta:
        verbose_name = "Касса"
        verbose_name_plural = "Кассы"
        ordering = ['name']
        permissions = [
            ("can_transfer_funds", "Может перемещать средства между кассами"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_till_type_display()}) - Баланс: {self.current_balance}"

    def clean(self):
        super().clean()
        if (self.is_default_for_cash or self.is_default_for_card) and self.till_type != self.TYPE_RETAIL_POINT:
            raise ValidationError({'till_type': "Кассой по умолчанию для приема платежей от заказов может быть только 'Касса торговой точки'."})
        
        if self.is_default_for_cash and self.till_type == self.TYPE_RETAIL_POINT:
            if CashRegister.objects.filter(is_default_for_cash=True, till_type=self.TYPE_RETAIL_POINT).exclude(pk=self.pk).exists():
                raise ValidationError({'is_default_for_cash': 'Уже существует другая касса торговой точки по умолчанию для наличных.'})
        
        if self.is_default_for_card and self.till_type == self.TYPE_RETAIL_POINT:
            if CashRegister.objects.filter(is_default_for_card=True, till_type=self.TYPE_RETAIL_POINT).exclude(pk=self.pk).exists():
                raise ValidationError({'is_default_for_card': 'Уже существует другая касса торговой точки по умолчанию для карт.'})
        
        if self.is_gko_for_supply_payment and self.till_type != self.TYPE_MAIN_ORGANIZATION:
            raise ValidationError({'is_gko_for_supply_payment': "Флаг 'ГКО для оплаты поставок' может быть установлен только для касс с типом 'Главная касса организации'."})


# Модель CashTransaction (Кассовая транзакция) - БЕЗ ИЗМЕНЕНИЙ
class CashTransaction(models.Model):
    TRANSACTION_TYPE_INCOME = 'income'; TRANSACTION_TYPE_EXPENSE = 'expense'
    TRANSACTION_TYPE_TRANSFER_OUT = 'transfer_out'; TRANSACTION_TYPE_TRANSFER_IN = 'transfer_in'
    TRANSACTION_TYPES = [
        (TRANSACTION_TYPE_INCOME, 'Приход (от заказа/внешний)'), (TRANSACTION_TYPE_EXPENSE, 'Расход (внешний)'),
        (TRANSACTION_TYPE_TRANSFER_OUT, 'Перемещение (Расход)'), (TRANSACTION_TYPE_TRANSFER_IN, 'Перемещение (Приход)'),
    ]
    PAYMENT_METHOD_CASH = 'cash'; PAYMENT_METHOD_CARD = 'card'; PAYMENT_METHOD_TRANSFER = 'transfer'
    PAYMENT_METHODS = [
        (PAYMENT_METHOD_CASH, 'Наличные'), (PAYMENT_METHOD_CARD, 'Банковская карта'),
        (PAYMENT_METHOD_TRANSFER, 'Внутреннее перемещение'),
    ]
    cash_register = models.ForeignKey(CashRegister, on_delete=models.PROTECT, related_name='transactions', verbose_name="Касса")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, verbose_name="Тип транзакции")
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, verbose_name="Метод операции" )
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Сумма")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Дата и время операции")
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='cash_transactions', verbose_name="Сотрудник")
    description = models.TextField(blank=True, null=True, verbose_name="Описание/Комментарий")
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='cash_transactions', verbose_name="Заказ (если приход от заказа)")
    expense_category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='cash_transactions', verbose_name="Статья расхода (если расход)")
    paired_transfer_transaction = models.OneToOneField('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='reverse_paired_transfer', verbose_name="Парная транзакция перемещения")
    
    class Meta:
        verbose_name = "Кассовая транзакция"
        verbose_name_plural = "Кассовые транзакции"
        ordering = ['-timestamp']
        permissions = [
            ('can_view_gko_cash_transactions', "Может просматривать транзакции ГКО"),
        ]
    
    def __str__(self): 
        return f"{self.get_transaction_type_display()} на {self.amount} в {self.cash_register.name} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            with transaction.atomic():
                cash_reg = CashRegister.objects.select_for_update().get(pk=self.cash_register.pk)
                if self.transaction_type == self.TRANSACTION_TYPE_INCOME or self.transaction_type == self.TRANSACTION_TYPE_TRANSFER_IN:
                    cash_reg.current_balance += self.amount
                elif self.transaction_type == self.TRANSACTION_TYPE_EXPENSE or self.transaction_type == self.TRANSACTION_TYPE_TRANSFER_OUT:
                    cash_reg.current_balance -= self.amount
                cash_reg.save(update_fields=['current_balance'])

# Модель CashOverviewReportProxy - БЕЗ ИЗМЕНЕНИЙ
class CashOverviewReportProxy(models.Model):
    class Meta:
        managed = False
        verbose_name = "Обзор кассы (Отчет)"
        verbose_name_plural = "Обзор кассы (Отчет)"