# F:\CRM 2.0\ERP\orders\models.py
from django.db import models
from django.db import transaction # Оставляем, если предполагается использование
from django.conf import settings
from django.core.exceptions import ValidationError
# from django.utils import timezone # Не используется напрямую здесь
from decimal import Decimal, ROUND_HALF_UP

from products.models import Product
from clients.models import Client
from cash_register.models import CashRegister # CashTransaction не используется напрямую

class OrderType(models.Model):
    TYPE_REPAIR = "Ремонт"
    TYPE_SALE = "Продажа"
    TYPE_UNDEFINED = "Определить"

    name = models.CharField(max_length=100, unique=True, verbose_name="Название типа заказа")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")

    class Meta:
        verbose_name = "Тип заказа"
        verbose_name_plural = "Типы заказов"
        ordering = ['name']

    def __str__(self):
        return self.name

class Service(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Название услуги")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена услуги")

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"
        ordering = ['name']

    def __str__(self):
        return self.name

class Order(models.Model):
    STATUS_NEW = 'new'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_READY = 'ready'
    STATUS_ISSUED = 'issued'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_NEW, 'Новый'),
        (STATUS_IN_PROGRESS, 'В работе'),
        (STATUS_READY, 'Готов'),
        (STATUS_ISSUED, 'Выдан'),
        (STATUS_CANCELLED, 'Отменен'),
    ]

    ORDER_PAYMENT_METHOD_CASH = 'cash'
    ORDER_PAYMENT_METHOD_CARD = 'card'
    ORDER_PAYMENT_METHOD_CHOICES = [
        (ORDER_PAYMENT_METHOD_CASH, 'Наличные'),
        (ORDER_PAYMENT_METHOD_CARD, 'Карта'),
    ]

    order_type = models.ForeignKey(OrderType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Тип заказа")
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='managed_orders',
        verbose_name="Менеджер"
    )
    performer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='performed_orders',
        verbose_name="Исполнитель"
    )
    repaired_item = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Изделие"
    )
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='orders', verbose_name="Клиент")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW, verbose_name="Статус заказа")
    payment_method_on_closure = models.CharField(
        max_length=20,
        choices=ORDER_PAYMENT_METHOD_CHOICES,
        null=True,
        blank=True,
        verbose_name="Метод оплаты при закрытии"
    )
    target_cash_register = models.ForeignKey(
        CashRegister,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Касса для зачисления (авто)"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    notes = models.TextField(blank=True, null=True, verbose_name="Примечания к заказу")

    _previous_status = None

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-created_at']
        permissions = [
            ("can_change_order_type_dynamically", "Может изменять тип заказа (динамически)"),
            ("can_view_target_cash_register", "Может видеть кассу для зачисления в заказе"),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._previous_status = self.status if self.pk else None

    def __str__(self):
        return f"Заказ №{self.id or 'Новый'} от {self.created_at.strftime('%d.%m.%Y %H:%M') if self.pk else ' еще не создан'}"

    def calculate_total_amount(self):
        total = Decimal('0.00')
        if self.pk:
            for item in self.product_items.all():
                item_total = item.get_item_total()
                if item_total is not None: total += item_total
            for item in self.service_items.all():
                item_total = item.get_item_total()
                if item_total is not None: total += item_total
        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def determine_and_set_order_type(self):
        original_order_type = self.order_type
        if not self.pk:
            try:
                undefined_type = OrderType.objects.get(name=OrderType.TYPE_UNDEFINED)
                self.order_type = undefined_type
                return original_order_type != self.order_type
            except OrderType.DoesNotExist:
                self.order_type = None
                return original_order_type != self.order_type
        if self.status == self.STATUS_ISSUED and self._previous_status == self.STATUS_ISSUED:
            return False
        try:
            repair_type_obj = OrderType.objects.get(name=OrderType.TYPE_REPAIR)
            sale_type_obj = OrderType.objects.get(name=OrderType.TYPE_SALE)
            undefined_type_obj = OrderType.objects.get(name=OrderType.TYPE_UNDEFINED)
        except OrderType.DoesNotExist:
            return False
        has_services = self.service_items.exists()
        has_products = self.product_items.exists()
        determined_type = undefined_type_obj
        if has_services:
            determined_type = repair_type_obj
        elif has_products:
            determined_type = sale_type_obj
        if self.order_type != determined_type:
            self.order_type = determined_type
            return True
        return False

    def get_status_display_for_key(self, status_key):
        if not hasattr(self.__class__, '_status_choices_map_cache'):
            self.__class__._status_choices_map_cache = dict(self.STATUS_CHOICES)
        return self.__class__._status_choices_map_cache.get(status_key, status_key)

    def clean(self):
        super().clean()

        # 1. Новый заказ не может быть сразу "Выдан"
        if not self.pk and self.status == self.STATUS_ISSUED:
            raise ValidationError(
                "Новый заказ не может быть сразу создан со статусом 'Выдан'. "
                "Пожалуйста, выберите другой начальный статус."
            )

        # 2. Если статус "Выдан", метод оплаты должен быть указан
        if self.status == self.STATUS_ISSUED and not self.payment_method_on_closure:
            raise ValidationError({
                'payment_method_on_closure': ValidationError(
                    f"Метод оплаты должен быть указан для статуса '{self.get_status_display()}'.",
                    code='payment_method_required_for_issue'
                )
            })

        # 3. Валидация для исполнителя
        if self.order_type and self.order_type.name == OrderType.TYPE_REPAIR:
            if self.status != self.STATUS_NEW and not self.performer:
                status_new_display_name = self.get_status_display_for_key(self.STATUS_NEW)
                raise ValidationError({
                    'performer': ValidationError(
                        f"Поле 'Исполнитель' обязательно для типа заказа '{OrderType.TYPE_REPAIR}', "
                        f"если статус не '{status_new_display_name}'.",
                        code='performer_required_for_repair_if_not_new_model' # Уникальный код ошибки
                    )
                })

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._previous_status = self.status


class OrderProductItem(models.Model):
    order = models.ForeignKey(Order, related_name='product_items', on_delete=models.CASCADE, verbose_name="Заказ")
    product = models.ForeignKey(Product, related_name='order_product_items', on_delete=models.PROTECT, verbose_name="Товар")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена товара на момент заказа", null=True, blank=True)
    cost_price_at_sale = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Себестоимость на момент продажи (FIFO)", null=True, blank=True
    )
    class Meta:
        verbose_name = "Позиция товара в заказе"
        verbose_name_plural = "Позиции товаров в заказе"
    def __str__(self):
        product_name = self.product.name if self.product else "Товар не указан"
        order_id_str = str(self.order_id) if self.order_id else "неизв. заказ"
        return f"{product_name} ({self.quantity} шт.) в заказе №{order_id_str}"
    def get_item_total(self):
        if self.price_at_order is not None and self.quantity is not None and self.quantity > 0:
            price = Decimal(str(self.price_at_order))
            qty = Decimal(str(self.quantity))
            return (price * qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return Decimal('0.00')
    def save(self, *args, **kwargs):
        if self.pk is None or self.price_at_order is None or self.price_at_order == Decimal('0.00'):
            if self.product: self.price_at_order = self.product.retail_price
        super().save(*args, **kwargs)

class OrderServiceItem(models.Model):
    order = models.ForeignKey(Order, related_name='service_items', on_delete=models.CASCADE, verbose_name="Заказ")
    service = models.ForeignKey(Service, related_name='order_service_items', on_delete=models.PROTECT, verbose_name="Услуга")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена услуги на момент заказа", null=True, blank=True)
    class Meta:
        verbose_name = "Позиция услуги в заказе"
        verbose_name_plural = "Позиции услуг в заказе"
    def __str__(self):
        service_name = self.service.name if self.service else "Услуга не указана"
        order_id_str = str(self.order_id) if self.order_id else "неизв. заказ"
        return f"{service_name} ({self.quantity} шт.) в заказе №{order_id_str}"
    def get_item_total(self):
        if self.price_at_order is not None and self.quantity is not None and self.quantity > 0:
            price = Decimal(str(self.price_at_order))
            qty = Decimal(str(self.quantity))
            return (price * qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return Decimal('0.00')
    def save(self, *args, **kwargs):
        if self.pk is None or self.price_at_order is None or self.price_at_order == Decimal('0.00'):
            if self.service: self.price_at_order = self.service.price
        super().save(*args, **kwargs)