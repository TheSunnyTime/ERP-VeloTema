# F:\CRM 2.0\ERP\orders\models.py
from django.db import models
# transaction не используется в этом файле напрямую, если только не в закомментированном коде или неявных операциях.
# Если он не нужен, можно убрать. Оставляю на всякий случай, если где-то есть неявное использование.
from django.db import transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone # Не используется напрямую в этом файле, но может быть полезен для будущих доработок.
from decimal import Decimal, ROUND_HALF_UP

from products.models import Product
from clients.models import Client
from cash_register.models import CashTransaction, CashRegister # CashTransaction не используется напрямую, но CashRegister используется.
# Модели из salary_management здесь не используются, их импорт можно убрать.
# from salary_management.models import EmployeeRate, SalaryCalculation, SalaryCalculationDetail


class OrderType(models.Model):
    # Константы для имен типов заказов
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
        # null=True для CharField обычно заменяется default="" и blank=True.
        # Если null=True критично, оставляем. Иначе можно default="".
        default="", # Добавил default, если null=True не является строгим требованием
        verbose_name="Изделие"
    )
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='orders', verbose_name="Клиент")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW, verbose_name="Статус заказа")
    payment_method_on_closure = models.CharField(
        max_length=20,
        choices=ORDER_PAYMENT_METHOD_CHOICES,
        null=True, # null=True здесь оправдан, т.к. метод оплаты указывается только при закрытии
        blank=True,
        verbose_name="Метод оплаты при закрытии"
    )
    target_cash_register = models.ForeignKey(
        CashRegister,
        on_delete=models.SET_NULL,
        null=True, # null=True здесь оправдан, т.к. касса определяется при закрытии
        blank=True,
        verbose_name="Касса для зачисления (авто)"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    notes = models.TextField(blank=True, null=True, verbose_name="Примечания к заказу")

    _previous_status = None # Для отслеживания изменения статуса

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
        # Сохраняем начальное значение статуса, если объект уже существует в БД
        self._previous_status = self.status if self.pk else None


    def __str__(self):
        return f"Заказ №{self.id or 'Новый'} от {self.created_at.strftime('%d.%m.%Y %H:%M') if self.pk else ' еще не создан'}"

    def calculate_total_amount(self):
        total = Decimal('0.00')
        if self.pk: # Рассчитываем только для сохраненных заказов, имеющих связанные элементы
            for item in self.product_items.all():
                item_total = item.get_item_total()
                if item_total is not None:
                    total += item_total
            for item in self.service_items.all():
                item_total = item.get_item_total()
                if item_total is not None:
                    total += item_total
        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def determine_and_set_order_type(self):
        """
        Определяет и устанавливает тип заказа на основе наличия товаров или услуг.
        Возвращает True, если тип был изменен, иначе False.
        """
        original_order_type = self.order_type

        if not self.pk: # Для нового, еще не сохраненного заказа
            try:
                undefined_type = OrderType.objects.get(name=OrderType.TYPE_UNDEFINED)
                self.order_type = undefined_type
                return original_order_type != self.order_type
            except OrderType.DoesNotExist:
                self.order_type = None # Или логировать ошибку, т.к. тип "Определить" должен существовать
                return original_order_type != self.order_type

        # Не переопределять тип для уже выданного заказа, если статус не менялся с "Выдан"
        if self.status == self.STATUS_ISSUED and self._previous_status == self.STATUS_ISSUED:
            return False

        try:
            # Получаем типы один раз для эффективности, если они часто используются
            # Можно также кешировать их на уровне класса или модуля, если OrderType редко меняются
            repair_type_obj = OrderType.objects.get(name=OrderType.TYPE_REPAIR)
            sale_type_obj = OrderType.objects.get(name=OrderType.TYPE_SALE)
            undefined_type_obj = OrderType.objects.get(name=OrderType.TYPE_UNDEFINED)
        except OrderType.DoesNotExist:
            # Логировать ошибку: один из базовых типов заказа отсутствует в БД
            return False # Не можем определить тип

        has_services = self.service_items.exists()
        has_products = self.product_items.exists()

        determined_type = undefined_type_obj # По умолчанию
        if has_services:
            determined_type = repair_type_obj
        elif has_products: # Только если нет услуг, но есть товары
            determined_type = sale_type_obj

        if self.order_type != determined_type:
            self.order_type = determined_type
            return True
        return False

    def get_status_display_for_key(self, status_key):
        """Вспомогательный метод для получения отображаемого имени статуса по ключу."""
        # Кэшируем словарь для небольшого повышения производительности, если метод вызывается часто
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
        if self.order_type:
            # Используем константу из OrderType
            if self.order_type.name == OrderType.TYPE_REPAIR:
                if self.status != self.STATUS_NEW and not self.performer:
                    status_new_display_name = self.get_status_display_for_key(self.STATUS_NEW)
                    raise ValidationError({
                        'performer': ValidationError(
                            f"Поле 'Исполнитель' обязательно для типа заказа '{OrderType.TYPE_REPAIR}', "
                            f"если статус не '{status_new_display_name}'.",
                            code='performer_required_for_repair_if_not_new_model'
                        )
                    })
        # Нет необходимости в try-except AttributeError для self.order_type.name,
        # так как if self.order_type: уже проверяет, что order_type не None.


    def save(self, *args, **kwargs):
        # Логика _previous_status должна быть до super().save(), если мы хотим сравнить
        # текущее состояние с тем, что было до любых изменений в этом вызове save.
        # Однако, если _previous_status нужен для отслеживания состояния из БД перед этим сохранением,
        # то __init__ и обновление _previous_status после super().save() - правильный подход.
        # Для определения, был ли статус изменен с НЕ-Выдан на Выдан, текущая логика с __init__ и
        # обновлением _previous_status в конце save - корректна.

        # Если нужно выполнить какие-то действия перед сохранением на основе _previous_status,
        # то _previous_status должен быть установлен в __init__ и, возможно, не меняться до конца save.
        # Сейчас _previous_status отражает состояние объекта *после* последнего успешного сохранения.

        super().save(*args, **kwargs)
        # Обновляем _previous_status после успешного сохранения, чтобы он отражал текущее состояние в БД
        self._previous_status = self.status


class OrderProductItem(models.Model):
    order = models.ForeignKey(Order, related_name='product_items', on_delete=models.CASCADE, verbose_name="Заказ")
    product = models.ForeignKey(Product, related_name='order_product_items', on_delete=models.PROTECT, verbose_name="Товар")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена товара на момент заказа", null=True, blank=True)
    cost_price_at_sale = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Себестоимость на момент продажи (FIFO)", # Изменил "заказа" на "продажи" для ясности
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Позиция товара в заказе"
        verbose_name_plural = "Позиции товаров в заказе"
        # unique_together = ['order', 'product'] # Рассмотреть, если один и тот же товар не должен добавляться дважды

    def __str__(self):
        product_name = self.product.name if self.product else "Товар не указан"
        order_id_str = str(self.order_id) if self.order_id else "неизв. заказ"
        return f"{product_name} ({self.quantity} шт.) в заказе №{order_id_str}"

    def get_item_total(self):
        if self.price_at_order is not None and self.quantity is not None and self.quantity > 0:
            # Убедимся, что работаем с Decimal
            price = Decimal(str(self.price_at_order))
            qty = Decimal(str(self.quantity)) # quantity уже PositiveIntegerField, но для единообразия
            return (price * qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return Decimal('0.00')

    def save(self, *args, **kwargs):
        if self.pk is None or self.price_at_order is None or self.price_at_order == Decimal('0.00'): # При создании или если цена не установлена
            if self.product:
                self.price_at_order = self.product.retail_price
        # cost_price_at_sale устанавливается внешней логикой (FIFO)
        super().save(*args, **kwargs)


class OrderServiceItem(models.Model):
    order = models.ForeignKey(Order, related_name='service_items', on_delete=models.CASCADE, verbose_name="Заказ")
    service = models.ForeignKey(Service, related_name='order_service_items', on_delete=models.PROTECT, verbose_name="Услуга")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена услуги на момент заказа", null=True, blank=True)

    class Meta:
        verbose_name = "Позиция услуги в заказе"
        verbose_name_plural = "Позиции услуг в заказе"
        # unique_together = ['order', 'service'] # Рассмотреть, если одна и та же услуга не должна добавляться дважды

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
        if self.pk is None or self.price_at_order is None or self.price_at_order == Decimal('0.00'): # При создании или если цена не установлена
            if self.service:
                self.price_at_order = self.service.price
        super().save(*args, **kwargs)