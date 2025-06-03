from django.db import models
from django.core.exceptions import ValidationError
import re # Для валидации HEX-кода

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