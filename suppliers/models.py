# suppliers/models.py
from django.db import models, transaction # <--- Убедись, что transaction здесь
from django.db.models import F # <--- Убедись, что F здесь
from django.conf import settings
from django.utils import timezone # Для default=timezone.now
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
    STATUS_PARTIALLY_RECEIVED = 'partially_received'
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

    _previous_status = None 

    class Meta:
        verbose_name = "Поставка (Приход товара)"
        verbose_name_plural = "Поставки (Приходы товара)"
        ordering = ['-receipt_date', '-created_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._previous_status = self.status 

    def __str__(self):
        return f"Поставка №{self.id or 'Новая'} от {self.supplier.name} ({self.receipt_date.strftime('%d.%m.%Y')})"

    def update_stock_on_received(self):
        if self.status == self.STATUS_RECEIVED:
            with transaction.atomic():
                print(f"[Supply UpdateStock] Начинаем обновление остатков для поставки #{self.id}")
                updated_any_product = False
                for item in self.items.all(): 
                    product_instance = item.product
                    print(f"[Supply UpdateStock] Обработка товара: {product_instance.name}, приход: {item.quantity_received}")
                    
                    product_to_update = Product.objects.select_for_update().get(pk=product_instance.pk) 
                    
                    product_to_update.stock_quantity = F('stock_quantity') + item.quantity_received
                    # product_to_update.cost_price НЕ МЕНЯЕМ ЗДЕСЬ (согласно Варианту 2, который ты выбрал)
                    
                    update_fields_list = ['stock_quantity']
                    if hasattr(product_to_update, 'updated_at'):
                         update_fields_list.append('updated_at')

                    product_to_update.save(update_fields=update_fields_list)
                    updated_any_product = True
                    
                    refreshed_product = Product.objects.get(pk=product_instance.pk)
                    print(f"[Supply UpdateStock] Обновлены остатки для {refreshed_product.name}: +{item.quantity_received}. "
                          f"Себестоимость этой партии: {item.cost_price_per_unit}. "
                          f"Основная себестоимость товара в карточке (Product.cost_price) НЕ ИЗМЕНЕНА: {refreshed_product.cost_price}. "
                          f"Текущий общий остаток: {refreshed_product.stock_quantity}")
                if not updated_any_product:
                    print(f"[Supply UpdateStock] Поставка #{self.id} не содержит позиций для обновления остатков.")
        else:
            print(f"[Supply UpdateStock] Статус поставки #{self.id} не '{self.STATUS_RECEIVED}', обновление остатков не требуется. Текущий статус: {self.status}")

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        print(f"[Supply Save] Сохранение поставки #{self.pk}. Старый статус (из _previous_status): {self._previous_status}, Новый статус (из формы/кода): {self.status}")
        
        super().save(*args, **kwargs) 
        
        current_status_in_db = self.status # После super().save() self.status должен быть актуальным
        if not is_new and self.pk: # Если объект уже существовал, можно дополнительно перечитать статус из БД для уверенности
             try:
                current_db_status = Supply.objects.get(pk=self.pk).status
                if self.status != current_db_status:
                     print(f"[Supply Save] Статус в объекте ({self.status}) отличается от статуса в БД ({current_db_status}) после super().save(). Используем из БД.")
                     self.status = current_db_status 
             except Supply.DoesNotExist:
                print(f"[Supply Save] Объект Supply #{self.pk} не найден в БД после super().save(). Пропуск update_stock_on_received.")
                self._previous_status = self.status # Обновляем, чтобы избежать повторного вызова если объект создается и сразу удаляется
                return

        just_became_received = (not is_new and self.status == self.STATUS_RECEIVED and self._previous_status != self.STATUS_RECEIVED)
        new_and_received = (is_new and self.status == self.STATUS_RECEIVED)

        if just_became_received or new_and_received:
            print(f"[Supply Save] Статус изменился на '{self.STATUS_RECEIVED}' или новый и '{self.STATUS_RECEIVED}'. Вызов update_stock_on_received для поставки #{self.id}.")
            self.update_stock_on_received() 
        else:
            print(f"[Supply Save] Условия для вызова update_stock_on_received не выполнены для поставки #{self.pk}.")
            print(f"[Supply Save] just_became_received: {just_became_received}, new_and_received: {new_and_received}")
            print(f"[Supply Save] current status: {self.status}, _previous_status: {self._previous_status}, is_new: {is_new}")
        
        self._previous_status = self.status


class SupplyItem(models.Model):
    supply = models.ForeignKey(
        Supply, # Предполагается, что класс Supply определен ВЫШЕ в этом файле или импортирован
        on_delete=models.CASCADE,
        related_name='items', 
        verbose_name="Поставка"
    )
    product = models.ForeignKey(
        Product, # Предполагается, что класс Product импортирован (например, from products.models import Product)
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
        help_text="Сколько единиц из этой поставки еще осталось на складе",
        default=0  # Устанавливаем значение по умолчанию
    )

    class Meta:
        verbose_name = "Позиция поставки"
        verbose_name_plural = "Позиции поставки"
        unique_together = ('supply', 'product')

    def __str__(self):
        # Для большей надежности, если product или supply могут быть не связаны на момент вызова __str__
        product_name = self.product.name if self.product else "Товар не указан"
        supply_id_str = str(self.supply_id) if self.supply_id else "неизв. поставке" # Используем self.supply_id
        return f"{product_name} ({self.quantity_received} шт.) в поставке ID {supply_id_str}"

    def save(self, *args, **kwargs):
        # Если это новая запись (pk еще нет) 
        # и quantity_remaining_in_batch равно значению по умолчанию (0)
        # И при этом quantity_received > 0 (чтобы не устанавливать, если приход 0)
        if self.pk is None and self.quantity_remaining_in_batch == 0 and self.quantity_received and self.quantity_received > 0:
            self.quantity_remaining_in_batch = self.quantity_received
        super().save(*args, **kwargs)