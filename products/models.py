# F:\CRM 2.0\ERP\products\models.py

from django.db import models
from django.db.models import Sum, Q # <--- ДОБАВЛЕНО: Sum для подсчета суммы и Q для сложных фильтров
from decimal import Decimal

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
        default=Decimal('0.00'),
        verbose_name="Розничная цена"
    )
    cost_price = models.DecimalField( 
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Себестоимость" 
    )
    # Устаревшее поле - теперь считается автоматически из партий
    stock_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name="Остаток на складе (устаревшее)"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата последнего обновления")

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ['name'] 

    def __str__(self):
        return self.name
    
    @property
    def get_real_stock_quantity(self):
        """
        Считает реальный остаток товара из партий поставок
        """
        try:
            from suppliers.models import SupplyItem
            
            # Сначала проверяем ВСЕ партии этого товара
            all_batches = SupplyItem.objects.filter(product=self)
            print(f"ОТЛАДКА ОСТАТКИ: Товар {self.name} - всего партий: {all_batches.count()}")
            
            for batch in all_batches:
                print(f"ОТЛАДКА ОСТАТКИ: Партия {batch.id} - статус поставки: '{batch.supply.status}', остаток: {batch.quantity_remaining_in_batch}")
            
            # Теперь считаем только принятые поставки
            accepted_batches = SupplyItem.objects.filter(
                product=self,
                quantity_remaining_in_batch__gt=0,
                supply__status='received'  # Только принятые поставки!
            )
            
            print(f"ОТЛАДКА ОСТАТКИ: Товар {self.name} - принятых партий с остатками: {accepted_batches.count()}")
            
            real_stock = accepted_batches.aggregate(
                total=Sum('quantity_remaining_in_batch')
            )['total'] or 0
            
            print(f"ОТЛАДКА ОСТАТКИ: Товар {self.name} - реальный остаток (только принятые): {real_stock}")
            return real_stock
        except Exception as e:
            print(f"ОТЛАДКА ОСТАТКИ: Ошибка подсчета остатков для {self.name}: {e}")
            return 0

    @property
    def get_available_stock_quantity(self):
        """
        ИСПРАВЛЕННАЯ ВЕРСИЯ: Считает доступный остаток товара правильно
        Доступно = общий остаток - общий резерв
        """
        try:
            from suppliers.models import SupplyItem
            
            print(f"ОТЛАДКА ДОСТУПНО: Считаем доступный товар для {self.name}")
            
            # Берем только принятые поставки с остатками
            batches = SupplyItem.objects.filter(
                product=self,
                quantity_remaining_in_batch__gt=0,
                supply__status='received'  # Только принятые поставки!
            )
            
            total_stock = 0  # Общий остаток товара
            total_reserved = 0  # Общий резерв товара
            
            print(f"ОТЛАДКА ДОСТУПНО: Товар {self.name} - проверяем {batches.count()} принятых партий")
            
            for batch in batches:
                # Считаем остатки и резервы в каждой партии
                batch_stock = batch.quantity_remaining_in_batch
                batch_reserved = batch.reserved_quantity
                
                total_stock += batch_stock
                total_reserved += batch_reserved
                
                print(f"ОТЛАДКА ДОСТУПНО: Партия {batch.id} - остаток={batch_stock}, резерв={batch_reserved}")
            
            # ПРАВИЛЬНАЯ ФОРМУЛА: Доступно = общий остаток - общий резерв
            available = total_stock - total_reserved
            
            print(f"ОТЛАДКА ДОСТУПНО: Товар {self.name} - остаток={total_stock}, резерв={total_reserved}, доступно={available}")
            
            return max(0, available)  # Не может быть меньше 0
            
        except Exception as e:
            print(f"ОТЛАДКА ДОСТУПНО: Ошибка подсчета для {self.name}: {e}")
            return 0

    @property
    def total_retail_value_in_stock(self):
        retail = self.retail_price if self.retail_price is not None else Decimal('0.00')
        quantity = self.stock_quantity if self.stock_quantity is not None else 0
        return (retail * quantity).quantize(Decimal('0.01'))
