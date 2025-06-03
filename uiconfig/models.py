from django.db import models
from django.core.exceptions import ValidationError
import re # Для валидации HEX-кода
from suppliers.models import Supply # 
from django.utils.html import format_html

# Чтобы получить доступ к choices из модели Order, мы импортируем ее
# Это может создать небольшую зависимость, но для choices это обычно приемлемо.
# Если возникнут проблемы с циклическим импортом (маловероятно здесь),
# мы можем пересмотреть этот момент.
from orders.models import Order # Убедись, что путь импорта корректен

class OrderStatusColor(models.Model):
    # Получаем STATUS_CHOICES из модели Order
    # Мы будем использовать их для поля status_key, чтобы обеспечить согласованность
    # и удобство выбора в админке.
    ORDER_STATUS_CHOICES_FOR_COLOR = Order.STATUS_CHOICES

    status_key = models.CharField(
        max_length=20,
        unique=True,
        choices=ORDER_STATUS_CHOICES_FOR_COLOR, # Используем choices для удобства выбора в админке
        verbose_name="Статус заказа (ключ)"
    )
    # status_display_name убрал, так как choices в status_key уже дадут нам отображаемое имя.
    # Если понадобится отдельное поле, можем вернуть.

    hex_color = models.CharField(
        max_length=7,  # Для формата #RRGGBB
        default='#FFFFFF',  # Белый цвет по умолчанию
        verbose_name="HEX-код цвета", 
        help_text="Введите цвет в формате #RRGGBB (например, #FF0000 для красного)."
    )

    def clean(self):
        super().clean()
        # Валидация HEX-кода цвета
        if not re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', self.hex_color):
            raise ValidationError({
                'hex_color': 'Неверный формат HEX-кода цвета. Используйте #RRGGBB или #RGB.'
            })

    def __str__(self):
        # Для отображения в админке и других местах
        # Используем get_status_key_display() для получения человекочитаемого имени статуса из choices
        return f"Цвет для статуса: {self.get_status_key_display()} ({self.hex_color})"

    class Meta:
        verbose_name = "Цвет статуса заказа"
        verbose_name_plural = "Цвета статусов заказов"
        ordering = ['status_key'] # Сортируем по ключу статуса для порядка
        permissions = [
            ("can_manage_status_colors", "Может управлять цветами статусов заказов"),
        ] # <-- ДОБАВЛЕНО
class SupplyStatusColor(models.Model):
    STATUS_CHOICES = Supply.STATUS_CHOICES # Используем те же choices, что и в модели Supply

    status_key = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        unique=True, # Каждый статус может иметь только один цвет
        verbose_name="Ключ статуса поставки"
    )
    status_name = models.CharField(
        max_length=100,
        verbose_name="Наименование статуса (для отображения)",
        help_text="Например, 'Оприходовано', 'Ожидается'",
        blank=True # Можно оставить пустым, будет браться из choices
    )
    hex_color = models.CharField(
        max_length=7,
        default='#000000', # Черный по умолчанию
        verbose_name="Цвет HEX",
        help_text="Например, #FFFFFF для белого или #008000 для зеленого"
    )

    class Meta:
        verbose_name = "Цвет статуса поставки"
        verbose_name_plural = "Цвета статусов поставок"
        # Если у тебя есть кастомные права для OrderStatusColor, можно добавить аналогичные здесь
        # permissions = [
        #     ("view_supplystatuscolor", "Может просматривать цвета статусов поставок"),
        #     ("change_supplystatuscolor", "Может изменять цвета статусов поставок"),
        # ]

    def __str__(self):
        return self.get_status_key_display() # Отображает человекочитаемое имя статуса

    def save(self, *args, **kwargs):
        # Автоматически заполняем status_name, если он пуст
        if not self.status_name:
            self.status_name = self.get_status_key_display()
        super().save(*args, **kwargs)

    def colored_status_preview(self):
        if not self.hex_color:
            return self.status_name or self.get_status_key_display()
        return format_html(
            '<span style="background-color: {0}; padding: 3px 7px; border-radius: 4px; color: {1};"><strong>{2}</strong></span>',
            self.hex_color,
            '#ffffff' if int(self.hex_color[1:3], 16) * 0.299 + int(self.hex_color[3:5], 16) * 0.587 + int(self.hex_color[5:7], 16) * 0.114 < 128 else '#000000', # Выбор цвета текста (черный/белый) для контраста
            self.status_name or self.get_status_key_display()
        )
    colored_status_preview.short_description = 'Предпросмотр'
    colored_status_preview.allow_tags = True