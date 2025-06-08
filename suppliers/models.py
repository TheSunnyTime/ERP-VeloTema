# suppliers/models.py

from django.db import models, transaction
from django.db.models import F
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from products.models import Product # Убедись, что модель Product импортируется правильно

class Supplier(models.Model):
    name = models.CharField(
        max_length=255, 
        verbose_name="Наименование поставщика", 
        unique=True
    )
    contact_person_name = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name="ФИО контактного лица (общее)"
    )
    phone_number = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name="Основной телефон поставщика"
    )
    email = models.EmailField(
        max_length=255, 
        blank=True, 
        verbose_name="Email поставщика"
    )
    bank_account = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="Расчетный счет"
    )
    tax_id = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name="УНП/ИНН"
    )
    bank_details = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name="Наименование и адрес банка"
    )
    supplier_manager_name = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name="ФИО менеджера у поставщика"
    )
    supplier_manager_phone = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name="Конт. номер менеджера поставщика"
    )
    notes = models.TextField(
        blank=True, 
        verbose_name="Примечания/Комментарии"
    )
    is_active = models.BooleanField(
        default=True, 
        verbose_name="Активен"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Поставщик"
        verbose_name_plural = "Поставщики"
        ordering = ['name']
        permissions = [
            ("can_edit_supplier_notes", "Может редактировать примечания поставщика"),
            ("can_change_supplier_status", "Может изменять статус активности поставщика"),
        ]

    def __str__(self):
        return self.name


class Supply(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_EXPECTED = 'expected'
    STATUS_RECEIVED = 'received' 
    STATUS_PARTIALLY_RECEIVED = 'partially_received' # Учтем его тоже при отмене
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Черновик'),
        (STATUS_EXPECTED, 'Ожидается'),
        (STATUS_RECEIVED, 'Оприходовано'),
        (STATUS_PARTIALLY_RECEIVED, 'Частично оприходовано'),
        (STATUS_CANCELLED, 'Отменено'),
    ]

    supplier = models.ForeignKey(
        Supplier, 
        on_delete=models.PROTECT,
        related_name='supplies',
        verbose_name="Поставщик"
    )
    receipt_date = models.DateField(
        default=timezone.now,
        verbose_name="Дата прихода"
    )
    document_number = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="Номер документа поставщика"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="Статус поставки"
    )
    notes = models.TextField(blank=True, verbose_name="Примечания к поставке")
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_supplies',
        verbose_name="Создал запись"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания записи")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления записи")

    payment_transaction_created = models.BooleanField(
        default=False, 
        verbose_name="Расходная операция по оплате создана",
        help_text="Отмечается, когда для этой поставки была автоматически (через задачу) создана кассовая транзакция на оплату."
    )

    _previous_status = None 

    class Meta:
        verbose_name = "Поставка (Приход товара)"
        verbose_name_plural = "Поставки (Приходы товара)"
        ordering = ['-receipt_date', '-created_at']
        permissions = [
            ('can_edit_received_supply', "Может редактировать оприходованные поставки"),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._previous_status = self.status 

    def __str__(self):
        return f"Поставка №{self.id or 'Новая'} от {self.supplier.name} ({self.receipt_date.strftime('%d.%m.%Y')})"

    def get_total_cost(self):
        total = Decimal('0.00')
        # Используем select_related для оптимизации, если items часто дергаются
        for item in self.items.all(): # items - related_name
            total += item.quantity_received * item.cost_price_per_unit
        return total

    def update_stock_on_received(self):
        """
        Обновляет остатки товаров и Product.cost_price при оприходовании поставки.
        Увеличивает Product.stock_quantity.
        Устанавливает SupplyItem.quantity_remaining_in_batch равным SupplyItem.quantity_received.
        Обновляет Product.cost_price на значение item.cost_price_per_unit из этой поставки.
        """
        print(f"[Supply UpdateStock] Начинаем обновление остатков и себестоимости для поставки #{self.id}")
        with transaction.atomic():
            for item in self.items.select_related('product').all(): 
                product_instance = item.product
                print(f"[Supply UpdateStock] Обработка товара: {product_instance.name}, приход: {item.quantity_received}, себестоимость партии: {item.cost_price_per_unit}")
                
                product_to_update = Product.objects.select_for_update().get(pk=product_instance.pk) 
                
                original_stock = product_to_update.stock_quantity
                original_cost_price = product_to_update.cost_price # Запомним старую себестоимость для лога

                # Обновляем количество на складе
                product_to_update.stock_quantity = F('stock_quantity') + item.quantity_received
                
                # --- НОВОЕ: Обновляем Product.cost_price ---
                # Устанавливаем себестоимость товара равной себестоимости из этой (последней) партии
                product_to_update.cost_price = item.cost_price_per_unit 
                # --- КОНЕЦ НОВОГО ---
                
                update_fields_list = ['stock_quantity', 'cost_price'] # Добавили cost_price
                if hasattr(product_to_update, 'updated_at'):
                     update_fields_list.append('updated_at') # Обновляем и updated_at, если есть

                product_to_update.save(update_fields=update_fields_list)
                product_to_update.refresh_from_db() 
                
                item.quantity_remaining_in_batch = item.quantity_received
                item.save(update_fields=['quantity_remaining_in_batch'])
                
                print(f"[Supply UpdateStock] Обновлены данные для {product_to_update.name}: "
                      f"Остаток: было {original_stock}, стало {product_to_update.stock_quantity} (+{item.quantity_received}). "
                      f"Product.cost_price: было {original_cost_price}, стало {product_to_update.cost_price} (из партии ID {item.id}). "
                      f"Остаток в партии (SupplyItem {item.id}): {item.quantity_remaining_in_batch}")
        print(f"[Supply UpdateStock] Завершено обновление остатков и себестоимости для поставки #{self.id}")


    def _handle_cancellation(self):
        """
        Обрабатывает отмену поставки:
        - Откатывает изменения stock_quantity для товаров, если поставка была оприходована.
        - Обнуляет quantity_remaining_in_batch для всех позиций поставки.
        """
        print(f"[Supply Cancel] Обработка отмены поставки #{self.id}. Предыдущий статус: {self._previous_status}")
        with transaction.atomic():
            for item in self.items.select_related('product').all():
                # Блокируем строку продукта для обновления
                product_to_update = Product.objects.select_for_update().get(pk=item.product.pk)
                
                # Если предыдущий статус был "Оприходовано" или "Частично оприходовано",
                # то товары были на складе, и их нужно списать (вернуть).
                if self._previous_status in [self.STATUS_RECEIVED, self.STATUS_PARTIALLY_RECEIVED]:
                    original_stock = product_to_update.stock_quantity
                    product_to_update.stock_quantity = F('stock_quantity') - item.quantity_received
                    
                    update_fields_product = ['stock_quantity']
                    if hasattr(product_to_update, 'updated_at'):
                        update_fields_product.append('updated_at')
                    product_to_update.save(update_fields=update_fields_product)
                    product_to_update.refresh_from_db() 
                    print(f"[Supply Cancel] Откат остатков для {product_to_update.name}: "
                          f"было {original_stock}, списано {item.quantity_received}, стало {product_to_update.stock_quantity}")

                # Обнуляем остаток этой партии в SupplyItem, так как отмененная поставка
                # не должна участвовать в FIFO. Делаем это всегда при отмене.
                if item.quantity_remaining_in_batch > 0:
                    original_batch_remaining = item.quantity_remaining_in_batch
                    item.quantity_remaining_in_batch = 0
                    item.save(update_fields=['quantity_remaining_in_batch'])
                    print(f"[Supply Cancel] Обнулен quantity_remaining_in_batch для {item.product.name} в поставке {self.id} "
                          f"(было {original_batch_remaining}, стало 0)")
        print(f"[Supply Cancel] Завершена обработка отмены для поставки #{self.id}")


    def save(self, *args, **kwargs):
        # Логику вызова update_stock_on_received и _handle_cancellation ПОЛНОСТЬЮ УБРАЛИ ОТСЮДА.
        # Атрибут _previous_status экземпляра будет устанавливаться и использоваться в SupplyAdmin.
        
        # print(f"[Supply Save model] Сохранение Supply ID {self.pk}. Статус объекта перед super: {self.status}, _previous_status объекта: {getattr(self, '_previous_status', 'Not Set')}")
        super().save(*args, **kwargs)
        # print(f"[Supply Save model] Сохранено Supply ID {self.id}. Статус объекта после super: {self.status}")


class SupplyItem(models.Model):
    supply = models.ForeignKey(
        Supply, 
        on_delete=models.CASCADE,
        related_name='items', 
        verbose_name="Поставка"
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.PROTECT, 
        verbose_name="Товар"
    )
    quantity_received = models.PositiveIntegerField(verbose_name="Количество получено")
    cost_price_per_unit = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Себестоимость за единицу (в этой поставке)"
    )
    quantity_remaining_in_batch = models.PositiveIntegerField(
        verbose_name="Остаток из этой партии",
        help_text="Сколько единиц из этой поставки еще осталось на складе. Обновляется при оприходовании или отмене поставки.",
        default=0 
    )

    class Meta:
        verbose_name = "Позиция поставки"
        verbose_name_plural = "Позиции поставки"
        unique_together = ('supply', 'product')

    def __str__(self):
        product_name = self.product.name if self.product else "Товар не указан"
        supply_id_str = str(self.supply_id) if self.supply_id else "неизв. поставке"
        return f"{product_name} ({self.quantity_received} шт.) в поставке ID {supply_id_str}"

    def save(self, *args, **kwargs):
        # Логика установки quantity_remaining_in_batch при создании SupplyItem была здесь.
        # Теперь quantity_remaining_in_batch устанавливается в 0 по умолчанию,
        # и обновляется до quantity_received методом Supply.update_stock_on_received()
        # или до 0 методом Supply._handle_cancellation().
        # Это делает управление этим полем более централизованным и привязанным к статусу поставки.
        super().save(*args, **kwargs)