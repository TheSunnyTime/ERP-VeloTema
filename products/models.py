# F:\CRM 2.0\ERP\products\models.py

from django.db import models
from decimal import Decimal # Убедись, что Decimal импортирован

class Category(models.Model):
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
        default=Decimal('0.00'), # <--- ДОБАВЛЕН DEFAULT
        verbose_name="Розничная цена"
    )
    cost_price = models.DecimalField( 
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'), # <--- ДОБАВЛЕН DEFAULT
        verbose_name="Себестоимость" 
    )
    stock_quantity = models.PositiveIntegerField(
        default=0, # Этот default у тебя уже был, это хорошо
        verbose_name="Остаток на складе"
    )
    # Поле is_active, если оно нужно (по контексту проекта оно упоминалось)
    # is_active = models.BooleanField(default=True, verbose_name="Активен")

    # created_at можно добавить, если нужно отслеживать дату создания
    # created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата последнего обновления")


    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ['name'] 

    def __str__(self):
        return self.name
    
    @property
    def total_retail_value_in_stock(self):
        retail = self.retail_price if self.retail_price is not None else Decimal('0.00')
        quantity = self.stock_quantity if self.stock_quantity is not None else 0
        return (retail * quantity).quantize(Decimal('0.01'))