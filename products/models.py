from django.db import models

# Create your models here.
# CRM 2.0/ERP/products/models.py
from django.db import models

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
        blank=True,  # Поле может быть пустым
        null=True,   # и иметь значение NULL в базе (для не уникальных текстовых часто достаточно blank=True)
        verbose_name="Артикул"
    )
    category = models.ForeignKey(
        Category,
        related_name='products',
        on_delete=models.SET_NULL, # Если категорию удалят, у товаров это поле станет пустым (NULL)
        null=True,                 # Разрешаем полю быть пустым в базе данных
        blank=True,                # Поле может быть не заполнено в формах
        verbose_name="Категория"
    )
    retail_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Розничная цена"
    )
    cost_price = models.DecimalField( # Изменили имя на cost_price
        max_digits=10,
        decimal_places=2,
        verbose_name="Себестоимость"  # Изменили verbose_name
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