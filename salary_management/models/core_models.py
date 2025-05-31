from django.db import models
from django.conf import settings
from decimal import Decimal

class EmployeeRate(models.Model):
    ROLE_MANAGER = 'manager'
    ROLE_PERFORMER = 'performer'
    # ROLE_ANY = 'any' 

    ROLE_CHOICES = [
        (ROLE_MANAGER, 'Менеджер в заказе'),
        (ROLE_PERFORMER, 'Исполнитель в заказе'),
        # (ROLE_ANY, 'Любая роль в заказе'),
    ]

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        verbose_name="Сотрудник"
    )
    order_type = models.ForeignKey(
        'orders.OrderType', 
        on_delete=models.CASCADE, 
        verbose_name="Тип заказа"
    )
    role_in_order = models.CharField(
        max_length=15, 
        choices=ROLE_CHOICES, 
        verbose_name="Роль сотрудника в заказе"
        # default для этого поля был указан при миграции '0004...' как 'manager' для существующих строк
    )
    service_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        verbose_name="Процент от УСЛУГ (%)"
    )
    product_profit_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        verbose_name="Процент от ПРИБЫЛИ ТОВАРОВ (%)"
    )
    # --- ВОЗВРАЩАЕМ ПОЛЕ NOTES ---
    notes = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Примечания"
    )
    # --- КОНЕЦ ПОЛЯ NOTES ---
    
    is_active = models.BooleanField(default=True, verbose_name="Ставка активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Ставка сотрудника"
        verbose_name_plural = "Ставки сотрудников"
        # --- ВОЗВРАЩАЕМ ПОЛНЫЙ UNIQUE_TOGETHER И ORDERING ---
        unique_together = ('employee', 'order_type', 'role_in_order') 
        ordering = ['employee', 'order_type', 'role_in_order']
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---
    def __str__(self):
        return (f"{self.employee} для '{self.order_type.name if self.order_type else 'N/A'}' "
                f"(Роль: {self.get_role_in_order_display() if hasattr(self, 'role_in_order') else 'Не указана'}) | " # Проверка на hasattr
                f"Услуги: {self.service_percentage}%, Приб.тов.: {self.product_profit_percentage}%"
                f"{' (Активна)' if self.is_active else ' (Не активна)'}")


class SalaryCalculation(models.Model):
    # --- КОНСТАНТЫ И ВЫБОР ДЛЯ КОНТЕКСТА РОЛИ ---
    ROLE_CONTEXT_MANAGER = 'manager_earning'
    ROLE_CONTEXT_PERFORMER = 'performer_earning'
    # Можно добавить и другие, если понадобятся (например, 'general_bonus')
    
    ROLE_CONTEXT_CHOICES = [
        (ROLE_CONTEXT_MANAGER, 'Начисление как Менеджеру'),
        (ROLE_CONTEXT_PERFORMER, 'Начисление как Исполнителю'),
    ]
    # --- КОНЕЦ КОНСТАНТ И ВЫБОРА ---

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT, # Возможно, PROTECT лучше, чем CASCADE, для сохранения истории
        verbose_name="Сотрудник",
        related_name="sm_salary_calculations" 
    )
    order = models.ForeignKey( # Изменили с OneToOneField на ForeignKey, если может быть несколько расчетов на один заказ (для разных ролей/сотрудников)
        'orders.Order', 
        on_delete=models.CASCADE, # Если заказ удаляется, связанные расчеты тоже
        verbose_name="Заказ",
        # related_name убрал, чтобы не конфликтовать, если будет много SalaryCalculation на один Order
        # или можно оставить/изменить, если default 'salarycalculation_set' не устраивает
    )
    # --- НОВОЕ ПОЛЕ ДЛЯ КОНТЕКСТА РОЛИ ---
    role_context = models.CharField(
        max_length=20,
        choices=ROLE_CONTEXT_CHOICES,
        verbose_name="Контекст роли для начисления",
        # null=True, blank=True, # Если делаем обязательным, то при миграции спросит default
        # default=ROLE_CONTEXT_MANAGER # Или можно сделать так для существующих
    )
    # --- КОНЕЦ НОВОГО ПОЛЯ ---
    
    total_calculated_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Итоговая сумма начисления", # Изменил для ясности
        default=Decimal('0.00')
    )
    period_date = models.DateField(
        verbose_name="Дата отнесения к периоду",
        help_text="Дата, по которой это начисление попадет в зарплатный период (например, дата выдачи заказа)."
    )
    applied_base_rule_info = models.TextField(
        verbose_name="Основное примененное правило",
        help_text="Например: 'Ставка для Сотрудника X, тип заказа Y, роль Менеджер: 10% от прибыли товаров'",
        default="",
        blank=True # Позволим быть пустым
    )
    calculation_type = models.CharField(
        max_length=100,
        default="Сдельная оплата по заказу",
        verbose_name="Тип начисления"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания записи расчета"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления записи расчета"
    )

    class Meta:
        verbose_name = "Расчет зарплаты" # Убрал "(Зарплаты)" для краткости
        verbose_name_plural = "Расчеты зарплаты"
        # Обновляем unique_together, чтобы включить роль
        unique_together = ('employee', 'order', 'role_context') 
        ordering = ['-period_date', '-created_at', 'employee__username']
        # permissions = [ # Оставим пока без кастомных permissions
        # ("view_all_salary_calculations", "Может просматривать все расчеты зарплат"),
        # ]

    def __str__(self):
        employee_name = self.employee.first_name if self.employee.first_name else self.employee.username
        return (f"Начисление {employee_name} по заказу ID {self.order_id} "
                f"({self.get_role_context_display()}) на {self.total_calculated_amount} "
                f"(период: {self.period_date.strftime('%d.%m.%Y')})")

    # ... (property методы calculation_period_year и calculation_period_month остаются) ...
    @property
    def calculation_period_year(self):
        return self.period_date.year

    @property
    def calculation_period_month(self):
        return self.period_date.month

class SalaryPayment(models.Model):
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="Сотрудник",
        related_name="sm_salary_payments" # Добавил префикс sm_
    )
    payment_date = models.DateField(
        verbose_name="Дата выплаты"
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Сумма выплаты"
    )
    payment_for_year = models.IntegerField(verbose_name="Год периода выплаты")
    payment_for_month = models.IntegerField(verbose_name="Месяц периода выплаты")

    notes = models.TextField(
        blank=True,
        verbose_name="Комментарий к выплате"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания записи")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Зарегистрировал выплату",
        related_name="sm_registered_salary_payments" # Добавил префикс sm_
    )

    class Meta:
        verbose_name = "Выплата зарплаты (Зарплаты)" # Уточнил verbose_name
        verbose_name_plural = "Выплаты зарплаты"
        ordering = ['-payment_date', 'employee__username']
        # Права доступа теперь будут принадлежать этому приложению: salary_management.can_register_salary_payments
        permissions = [ 
            ("can_register_salary_payments", "Может регистрировать выплаты зарплаты"),
        ]

    def __str__(self):
        employee_name = self.employee.first_name if self.employee.first_name else self.employee.username
        return f"Выплата {employee_name} от {self.payment_date.strftime('%d.%m.%Y')} на сумму {self.amount_paid}"