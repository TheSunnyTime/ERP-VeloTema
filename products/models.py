from django.db import models

# Create your models here.
# CRM 2.0/ERP/products/models.py
from django.db import models
from decimal import Decimal

class Category(models.Model):
    # ... (твой код Category) ...
    name = models.CharField(
        max_length=150,
        unique=True,
        verbose_name="Название категории"
    )

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="Наименование товара"
    )
    sku = models.CharField(
        max_length=100,
        blank=True,
        null=True, 
        verbose_name="Артикул"
    )
    category = models.ForeignKey(
        Category,
        related_name='products',
        on_delete=models.SET_NULL,
        null=True, 
        blank=True,
        verbose_name="Категория"
    )
    retail_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Розничная цена"
    )
    # Убедись, что это поле называется cost_price после наших предыдущих переименований
    cost_price = models.DecimalField( 
        max_digits=10,
        decimal_places=2,
        verbose_name="Себестоимость" # Это бывшее wholesale_price
    )
    stock_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name="Остаток на складе"
    )

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"

    def __str__(self):
        return self.name

    # --- НОВЫЕ СВОЙСТВА ДЛЯ РАСЧЕТА СУММ ---
    @property
    def total_cost_value_in_stock(self):
        cost = self.cost_price if self.cost_price is not None else Decimal('0.00')
        quantity = self.stock_quantity if self.stock_quantity is not None else 0
        return (cost * quantity).quantize(Decimal('0.01'))

    @property
    def total_retail_value_in_stock(self):
        retail = self.retail_price if self.retail_price is not None else Decimal('0.00')
        quantity = self.stock_quantity if self.stock_quantity is not None else 0
        return (retail * quantity).quantize(Decimal('0.01'))
    # --- КОНЕЦ НОВЫХ СВОЙСТВ ---