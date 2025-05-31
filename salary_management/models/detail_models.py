# salary_management/models/detail_models.py
from django.db import models
from django.conf import settings # Может понадобиться для __str__ или других полей
from decimal import Decimal
from .core_models import SalaryCalculation # Важный импорт

# Определение SalaryCalculationDetail (которое ты перенесешь сюда)
class SalaryCalculationDetail(models.Model):
    salary_calculation = models.ForeignKey(
        SalaryCalculation,
        on_delete=models.CASCADE,
        related_name='service_details', # Можно назвать так, чтобы отличать от product_profit_details
        verbose_name="Основной расчет зарплаты"
    )
    order_service_item = models.ForeignKey(
        'orders.OrderServiceItem', 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Позиция услуги в заказе"
    )
    source_description = models.CharField(max_length=255, verbose_name="Источник начисления (описание)")
    base_amount_for_calc = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Базовая сумма для расчета")
    applied_percentage = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Примененный процент")
    earned_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Начислено")
    detail_type = models.CharField(max_length=50, default="service", verbose_name="Тип детализации")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания") # Добавил для консистентности

    class Meta:
        verbose_name = "Детализация ЗП по услуге"
        verbose_name_plural = "Детализации ЗП по услугам"
        ordering = ['-created_at']

    def __str__(self):
        employee_name = self.salary_calculation.employee.get_full_name() or self.salary_calculation.employee.username
        return f"Деталь (услуга) для {employee_name}: {self.source_description} - {self.earned_amount} руб."

# Твоя новая модель ProductSalaryDetail (оставляем как есть)
class ProductSalaryDetail(models.Model):
    salary_calculation = models.ForeignKey(
        SalaryCalculation,
        on_delete=models.CASCADE,
        related_name='product_profit_details',
        verbose_name="Основной расчет зарплаты"
    )
    # ... остальные поля ProductSalaryDetail ...
    order_product_item = models.ForeignKey(
        'orders.OrderProductItem', 
        on_delete=models.SET_NULL,
        null=True,
        blank=True, 
        verbose_name="Товарная позиция заказа"
    )
    product_name_snapshot = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name="Наименование товара (на момент расчета)"
    )
    product_price_at_sale = models.DecimalField(
        max_digits=10, decimal_places=2, 
        verbose_name="Цена продажи товара"
    )
    product_cost_at_sale = models.DecimalField(
        max_digits=10, decimal_places=2, 
        verbose_name="Себестоимость товара на момент продажи"
    )
    profit_from_item = models.DecimalField(
        max_digits=10, decimal_places=2, 
        verbose_name="Прибыль от товарной позиции"
    )
    applied_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, 
        verbose_name="Примененный % от прибыли"
    )
    earned_amount = models.DecimalField(
        max_digits=10, decimal_places=2, 
        verbose_name="Начислено с прибыли по товару"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания записи")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления записи")

    class Meta:
        verbose_name = "Детализация ЗП от прибыли по товару"
        verbose_name_plural = "Детализации ЗП от прибыли по товарам"
        ordering = ['-created_at']

    def __str__(self):
        employee_name = self.salary_calculation.employee.get_full_name() or self.salary_calculation.employee.username
        return (f"Деталь (приб.тов.) для {employee_name} по товару "
                f"'{self.product_name_snapshot or self.order_product_item}': {self.earned_amount} руб.")

    def save(self, *args, **kwargs):
        if self.order_product_item and not self.product_name_snapshot:
            self.product_name_snapshot = self.order_product_item.product.name
        super().save(*args, **kwargs)