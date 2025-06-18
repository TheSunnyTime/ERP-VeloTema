from django.db import models, transaction
from django.contrib import admin
from django.db.models import F, Q
from django.conf import settings
from django.utils import timezone
from datetime import timedelta # Добавлено для правила 24 часов
from decimal import Decimal
from products.models import Product # Убедись, что модель Product импортируется правильно

# Кастомное исключение для логики отмены
class CannotCancelError(ValueError):
    """Исключение, возникающее при невозможности отменить поставку."""
    pass

class Supplier(models.Model):
    # Модель Supplier остается без изменений из твоего предыдущего кода
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
    STATUS_EXPECTED = 'expected' # Статус "Ожидается" (когда заказано, в пути)
    STATUS_RECEIVED = 'received' # Статус "Оприходовано"
    # STATUS_PARTIALLY_RECEIVED УДАЛЕН
    STATUS_CANCELLED = 'cancelled' # Статус "Отменено"

    # Статусы, при которых товары считаются оприходованными
    # RECEIVED_STATUSES УДАЛЕН, т.к. теперь только один статус оприходования

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Черновик'),
        (STATUS_EXPECTED, 'Ожидается'),
        (STATUS_RECEIVED, 'Оприходовано'),
        # (STATUS_PARTIALLY_RECEIVED, 'Частично оприходовано') УДАЛЕН
        (STATUS_CANCELLED, 'Отменено'),
    ]

    supplier = models.ForeignKey(
        Supplier, 
        on_delete=models.PROTECT,
        related_name='supplies',
        verbose_name="Поставщик"
    )
    receipt_date = models.DateField( # Фактическая дата получения товаров
        default=timezone.now, # Можно оставить default, но при оприходовании будет важнее received_at
        verbose_name="Дата документа прихода" 
    )
    # НОВОЕ ПОЛЕ: Ожидаемая дата поставки
    expected_delivery_date = models.DateField(
        "Ожидаемая дата поставки",
        null=True,
        blank=True,
        db_index=True # Индекс для возможной фильтрации/сортировки
    )
    # НОВОЕ ПОЛЕ: Дата и время фактического оприходования
    received_at = models.DateTimeField(
        "Дата и время оприходования",
        null=True,
        blank=True,
        editable=False, # Заполняется автоматически, не редактируется пользователем напрямую
        help_text="Заполняется автоматически при первом переходе поставки в статус 'Оприходовано'."
    )
    document_number = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="Номер документа поставщика"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT, # Новая поставка по умолчанию "Черновик"
        verbose_name="Статус поставки",
        db_index=True
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

    # Этот атрибут будет устанавливаться в SupplyAdmin перед вызовом методов модели
    # для передачи предыдущего состояния статуса из БД.
    _previous_status_in_db = None 

    class Meta:
        verbose_name = "Поставка (Приход товара)"
        verbose_name_plural = "Поставки (Приходы товара)"
        ordering = ['-receipt_date', '-created_at'] # receipt_date здесь - дата документа
        permissions = [
            ('can_edit_received_supply', "Может редактировать оприходованные поставки"),
        ]

    def __str__(self):
        return f"Поставка №{self.id or 'Новая'} от {self.supplier.name} ({self.receipt_date.strftime('%d.%m.%Y') if self.receipt_date else 'дата не указана'})"

    def get_total_cost(self):
        """Рассчитывает общую стоимость поставки на основе позиций."""
        total = Decimal('0.00')
        # Используем select_related для оптимизации, если items часто дергаются
        for item in self.items.all(): # items - related_name из SupplyItem
            total += item.quantity_received * item.cost_price_per_unit
        return total

    def update_stock_on_received(self):
        """
        Обновляет остатки товаров и Product.cost_price при оприходовании поставки.
        Вызывается, когда статус меняется на STATUS_RECEIVED.
        Устанавливает self.received_at, если это первое оприходование.
        """
        print(f"[Supply UpdateStock] Поставка #{self.id}: Начало обновления остатков и себестоимости (статус: {self.status}).")
        
        if self.status != self.STATUS_RECEIVED:
            # Дополнительная проверка, хотя логика вызова должна это гарантировать
            print(f"[Supply UpdateStock] Поставка #{self.id}: ОШИБКА - метод вызван для неверного статуса '{self.status}'. Прерывание.")
            return

        with transaction.atomic():
            # Устанавливаем дату и время оприходования, если это первое оприходование
            if not self.received_at:
                self.received_at = timezone.now()
                # Сохраняем только это поле, чтобы не вызвать рекурсию save() и сигналы, если они есть
                super().save(update_fields=['received_at', 'updated_at']) 
                print(f"[Supply UpdateStock] Поставка #{self.id}: Установлена дата оприходования: {self.received_at}.")

            for item in self.items.select_related('product').all(): 
                product_to_update = Product.objects.select_for_update().get(pk=item.product.pk)
                
                print(f"[Supply UpdateStock] Поставка #{self.id}, Товар: {product_to_update.name} (ID: {product_to_update.id}). "
                      f"Приход: {item.quantity_received}, Себестоимость партии: {item.cost_price_per_unit}.")
                
                original_stock = product_to_update.stock_quantity
                original_cost_price = product_to_update.cost_price

                # 1. Обновляем количество на складе (Product.stock_quantity)
                product_to_update.stock_quantity = F('stock_quantity') + item.quantity_received
                
                # 2. Обновляем Product.cost_price на значение из этой (последней оприходованной) поставки
                product_to_update.cost_price = item.cost_price_per_unit 
                
                update_fields_product = ['stock_quantity', 'cost_price']
                product_to_update.updated_at = timezone.now() # Явное обновление updated_at
                update_fields_product.append('updated_at')

                product_to_update.save(update_fields=update_fields_product)
                product_to_update.refresh_from_db() # Обновляем объект из БД
                
                # 3. Устанавливаем остаток в партии (SupplyItem.quantity_remaining_in_batch)
                item.quantity_remaining_in_batch = item.quantity_received
                item.save(update_fields=['quantity_remaining_in_batch'])
                
                print(f"[Supply UpdateStock] Поставка #{self.id}, Товар: {product_to_update.name}. "
                      f"Остаток: было {original_stock}, стало {product_to_update.stock_quantity} (+{item.quantity_received}). "
                      f"Product.cost_price: было {original_cost_price}, стало {product_to_update.cost_price}. "
                      f"Остаток в партии (SupplyItem ID {item.id}): {item.quantity_remaining_in_batch}.")
        print(f"[Supply UpdateStock] Поставка #{self.id}: Завершено обновление остатков и себестоимости.")


    def _handle_cancellation_checks(self):
        """
        Проверяет, можно ли отменить оприходованную поставку.
        Выбрасывает CannotCancelError, если отмена невозможна.
        Использует self._previous_status_in_db, который должен быть установлен админкой.
        """
        print(f"[Supply CancelChecks] Поставка #{self.id}: Проверка возможности отмены. Предыдущий статус: {self._previous_status_in_db}.")

        if self._previous_status_in_db != self.STATUS_RECEIVED:
            # Эта проверка для случая, если метод вызван ошибочно не для отмены оприходованной поставки
            print(f"[Supply CancelChecks] Поставка #{self.id}: Проверка не требуется, предыдущий статус не был '{self.STATUS_RECEIVED}'.")
            return 

        # 1. Проверка правила 24 часов
        if self.received_at: # received_at должно быть установлено для оприходованной поставки
            if timezone.now() > self.received_at + timedelta(hours=24):
                error_msg = (f"Отмена поставки #{self.id} невозможна. Прошло более 24 часов с момента оприходования "
                             f"({self.received_at.strftime('%d.%m.%Y %H:%M:%S')}).")
                print(f"[Supply CancelChecks] Поставка #{self.id}: {error_msg}")
                raise CannotCancelError(error_msg)
        else:
            # Ситуация, когда _previous_status_in_db == STATUS_RECEIVED, но self.received_at не установлено.
            # Это аномалия, но лучше обработать.
            error_msg = f"Ошибка данных для поставки #{self.id}: статус был 'Оприходовано', но дата оприходования не установлена."
            print(f"[Supply CancelChecks] Поставка #{self.id}: {error_msg}")
            raise CannotCancelError(error_msg) # Или более специфическое исключение

        # 2. Проверка использования товаров из поставки
        for item_check in self.items.all():
            if item_check.quantity_remaining_in_batch < item_check.quantity_received:
                error_msg = (f"Отмена поставки #{self.id} невозможна. "
                             f"Товар '{item_check.product.name}' (ID: {item_check.product.id}) из этой партии был частично или полностью использован. "
                             f"Остаток в партии: {item_check.quantity_remaining_in_batch}, было оприходовано: {item_check.quantity_received}.")
                print(f"[Supply CancelChecks] Поставка #{self.id}: {error_msg}")
                raise CannotCancelError(error_msg)
        
        print(f"[Supply CancelChecks] Поставка #{self.id}: Все проверки для отмены пройдены успешно.")


    def _perform_cancellation_actions(self):
        """
        Выполняет действия по отмене оприходованной поставки:
        - Откатывает изменения Product.stock_quantity.
        - Обнуляет SupplyItem.quantity_remaining_in_batch.
        - Пересчитывает Product.cost_price.
        Вызывается после успешных проверок в _handle_cancellation_checks().
        """
        print(f"[Supply PerformCancel] Поставка #{self.id}: Начало выполнения действий по отмене.")
        
        if self._previous_status_in_db != self.STATUS_RECEIVED:
            print(f"[Supply PerformCancel] Поставка #{self.id}: Действия по отмене не требуются, предыдущий статус не был '{self.STATUS_RECEIVED}'. Прерывание.")
            return

        with transaction.atomic():
            products_for_cost_recalculation = set() # Собираем PK товаров для пересчета себестоимости

            for item in self.items.select_related('product').all():
                product_to_update = Product.objects.select_for_update().get(pk=item.product.pk)
                
                print(f"[Supply PerformCancel] Поставка #{self.id}, Товар: {product_to_update.name} (ID: {product_to_update.id}). "
                      f"Отмена прихода: {item.quantity_received}.")

                # 1. Откат общего остатка товара (Product.stock_quantity)
                # Уменьшаем на количество, которое было в этой отменяемой поставке
                original_stock = product_to_update.stock_quantity
                product_to_update.stock_quantity = F('stock_quantity') - item.quantity_received 
                
                update_fields_product = ['stock_quantity']
                product_to_update.updated_at = timezone.now()
                update_fields_product.append('updated_at')
                product_to_update.save(update_fields=update_fields_product)
                product_to_update.refresh_from_db() 
                print(f"[Supply PerformCancel] Поставка #{self.id}, Товар: {product_to_update.name}. "
                      f"Остаток: было {original_stock}, стало {product_to_update.stock_quantity} (-{item.quantity_received}).")

                # 2. Обнуление остатка этой партии в SupplyItem
                if item.quantity_remaining_in_batch > 0:
                    original_batch_remaining = item.quantity_remaining_in_batch
                    item.quantity_remaining_in_batch = 0
                    item.save(update_fields=['quantity_remaining_in_batch'])
                    print(f"[Supply PerformCancel] Поставка #{self.id}, Товар: {item.product.name}. "
                          f"Обнулен quantity_remaining_in_batch (было {original_batch_remaining}).")
                
                products_for_cost_recalculation.add(product_to_update.pk)

            # 3. Пересчет себестоимости для затронутых товаров
            if products_for_cost_recalculation:
                print(f"[Supply PerformCancel] Поставка #{self.id}: Пересчет себестоимости для товаров PKs: {products_for_cost_recalculation}.")
                for product_pk in products_for_cost_recalculation:
                    product_instance = Product.objects.select_for_update().get(pk=product_pk)
                    
                    # Ищем последнюю актуальную (оприходованную, не отмененную) поставку для этого товара,
                    # ИСКЛЮЧАЯ текущую отменяемую поставку (self.pk).
                    latest_valid_supply_item = SupplyItem.objects.filter(
                        product=product_instance,
                        supply__status=Supply.STATUS_RECEIVED # Только из оприходованных
                    ).exclude(
                        supply__pk=self.pk # Исключаем текущую отменяемую поставку
                    ).order_by('-supply__received_at', '-supply__created_at').first() # Сортируем по дате оприходования

                    new_cost_price = Product._meta.get_field('cost_price').get_default() # Берем default из модели Product
                    source_info = "установлена по умолчанию (0.00)"

                    if latest_valid_supply_item:
                        new_cost_price = latest_valid_supply_item.cost_price_per_unit
                        source_info = f"взята из поставки #{latest_valid_supply_item.supply.id} (товар ID {latest_valid_supply_item.id})"
                        print(f"[Supply PerformCancel] Поставка #{self.id}, Товар: {product_instance.name}. "
                              f"Новая себестоимость {new_cost_price} {source_info}.")
                    else:
                        print(f"[Supply PerformCancel] Поставка #{self.id}, Товар: {product_instance.name}. "
                              f"Актуальных оприходованных поставок не найдено. Себестоимость {new_cost_price} {source_info}.")
                    
                    if product_instance.cost_price != new_cost_price:
                        old_product_cost = product_instance.cost_price
                        product_instance.cost_price = new_cost_price
                        product_instance.updated_at = timezone.now()
                        product_instance.save(update_fields=['cost_price', 'updated_at'])
                        print(f"[Supply PerformCancel] Поставка #{self.id}, Товар: {product_instance.name}. "
                              f"Себестоимость обновлена: было {old_product_cost}, стало {product_instance.cost_price}.")
                    else:
                        print(f"[Supply PerformCancel] Поставка #{self.id}, Товар: {product_instance.name}. "
                              f"Себестоимость ({product_instance.cost_price}) не изменилась.")

        print(f"[Supply PerformCancel] Поставка #{self.id}: Завершено выполнение действий по отмене.")

    def save(self, *args, **kwargs):
        # Атрибут _previous_status_in_db экземпляра будет устанавливаться в SupplyAdmin.
        # Логика вызова update_stock_on_received, _handle_cancellation_checks, 
        # и _perform_cancellation_actions полностью управляется из SupplyAdmin.
        # Метод save() модели Supply не должен сам решать, когда их вызывать,
        # чтобы избежать проблем с порядком сохранения инлайнов и основного объекта.
        
        # Если нужно обновить updated_at при любом сохранении, можно сделать это здесь,
        # но обычно Django это делает автоматически, если auto_now=True.
        # self.updated_at = timezone.now() # Если auto_now=True, это избыточно и может конфликтовать.
        
        super().save(*args, **kwargs)


class SupplyItem(models.Model):
    supply = models.ForeignKey(
        Supply, 
        on_delete=models.CASCADE, # Если удаляется поставка, удаляются и ее позиции
        related_name='items', 
        verbose_name="Поставка"
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.PROTECT, # Защита от удаления товара, если он есть в поставках
        verbose_name="Товар"
    )
    quantity_received = models.PositiveIntegerField(
        verbose_name="Количество получено",
        help_text="Фактическое количество товара, полученное в этой поставке."
    )
    cost_price_per_unit = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Себестоимость за единицу (в этой поставке)"
    )
    quantity_remaining_in_batch = models.PositiveIntegerField(
        verbose_name="Остаток из этой партии на складе",
        help_text="Сколько единиц из этой конкретной поставки еще осталось на складе. Управляется автоматически.",
        default=0 # По умолчанию 0, обновляется при оприходовании или отмене.
    )
    reserved_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name="В резерве (шт.)",
        help_text="Сколько единиц из этой партии зарезервировано под заказы. Управляется автоматически."
    )

    class Meta:
        verbose_name = "Позиция поставки"
        verbose_name_plural = "Позиции поставки"
        unique_together = ('supply', 'product') # Уникальная пара "поставка-товар"
        ordering = ['product__name'] # Сортировка по наименованию товара в инлайнах

    def __str__(self):
        product_name = self.product.name if self.product else "Товар не указан"
        supply_id_str = str(self.supply_id) if self.supply_id else "неизв. поставке"
        return f"{product_name} ({self.quantity_received} шт.) в поставке ID {supply_id_str}"

    # Метод save() для SupplyItem остается стандартным.
    # Вся логика обновления quantity_remaining_in_batch управляется из методов модели Supply.