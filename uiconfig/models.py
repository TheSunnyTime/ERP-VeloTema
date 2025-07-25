# uiconfig/models.py
from django.db import models
from django.core.exceptions import ValidationError
import re # Для валидации HEX-кода
from django.utils.html import format_html
from django.core.validators import RegexValidator

# Импорты моделей, с которыми есть ForeignKey или OneToOneField
from suppliers.models import Supply 
from tasks.models import TaskStatus
from orders.models import Order # Убедись, что путь импорта корректен

class OrderStatusColor(models.Model):
    ORDER_STATUS_CHOICES_FOR_COLOR = Order.STATUS_CHOICES

    status_key = models.CharField(
        max_length=20,
        unique=True,
        choices=ORDER_STATUS_CHOICES_FOR_COLOR,
        verbose_name="Статус заказа (ключ)"
    )
    hex_color = models.CharField(
        max_length=7,
        default='#FFFFFF',
        verbose_name="HEX-код цвета", 
        help_text="Введите цвет в формате #RRGGBB (например, #FF0000 для красного)."
    )

    def clean(self):
        super().clean()
        if not re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', self.hex_color):
            raise ValidationError({
                'hex_color': 'Неверный формат HEX-кода цвета. Используйте #RRGGBB или #RGB.'
            })

    def __str__(self):
        return f"Цвет для статуса: {self.get_status_key_display()} ({self.hex_color})"

    class Meta:
        verbose_name = "Цвет статуса заказа"
        verbose_name_plural = "Цвета статусов заказов"
        ordering = ['status_key']
        permissions = [
            ("can_manage_status_colors", "Может управлять цветами статусов заказов"),
        ]

class SupplyStatusColor(models.Model):
    STATUS_CHOICES = Supply.STATUS_CHOICES

    status_key = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        unique=True,
        verbose_name="Ключ статуса поставки"
    )
    status_name = models.CharField( # Это поле можно было бы убрать, если get_status_key_display() достаточно
        max_length=100,
        verbose_name="Наименование статуса (для отображения)",
        help_text="Например, 'Оприходовано', 'Ожидается'",
        blank=True 
    )
    hex_color = models.CharField(
        max_length=7,
        default='#000000',
        verbose_name="Цвет HEX",
        help_text="Например, #FFFFFF для белого или #008000 для зеленого"
    )

    class Meta:
        verbose_name = "Цвет статуса поставки"
        verbose_name_plural = "Цвета статусов поставок"

    def __str__(self):
        return self.get_status_key_display()

    def save(self, *args, **kwargs):
        if not self.status_name:
            self.status_name = self.get_status_key_display()
        super().save(*args, **kwargs)

    def colored_status_preview(self): # Этот метод для админки, если он там используется
        if not self.hex_color:
            return self.status_name or self.get_status_key_display()
        # Логика определения цвета текста для контраста
        try:
            text_color = '#ffffff' if int(self.hex_color[1:3], 16) * 0.299 + int(self.hex_color[3:5], 16) * 0.587 + int(self.hex_color[5:7], 16) * 0.114 < 128 else '#000000'
        except (ValueError, IndexError): # На случай некорректного hex_color
            text_color = '#000000'
        return format_html(
            '<span style="background-color: {0}; padding: 3px 7px; border-radius: 4px; color: {1};"><strong>{2}</strong></span>',
            self.hex_color,
            text_color,
            self.status_name or self.get_status_key_display()
        )
    colored_status_preview.short_description = 'Предпросмотр'
    # colored_status_preview.allow_tags = True # allow_tags устарело

class TaskStatusColor(models.Model):
    task_status = models.OneToOneField(
        TaskStatus,
        on_delete=models.CASCADE,
        verbose_name="Статус задачи",
        unique=True 
    )
    hex_color = models.CharField(
        max_length=7, 
        default='#FFFFFF', 
        verbose_name="HEX цвет", 
        help_text="Например, #RRGGBB"
    )

    class Meta:
        verbose_name = "Цвет статуса задачи"
        verbose_name_plural = "Цвета статусов задач"
        ordering = ['task_status__name'] 

    def __str__(self):
        return f"{self.task_status.name if self.task_status else 'Статус не выбран'} - {self.hex_color}"

    def get_status_name_for_admin_display(self):
        return self.task_status.name if self.task_status else "Статус не выбран"
    get_status_name_for_admin_display.short_description = "Статус задачи"
    get_status_name_for_admin_display.admin_order_field = 'task_status__name'

class OrderDueDateColorRule(models.Model):
    OPERATOR_LTE = 'lte'  # Меньше или равно ( <= days_threshold )
    OPERATOR_GTE = 'gte'  # Больше или равно ( >= days_threshold )
    OPERATOR_EQ = 'eq'    # Равно ( == days_threshold )

    COMPARISON_OPERATOR_CHOICES = [
        (OPERATOR_LTE, 'Осталось/Просрочено дней <= Порога'), # Если порог отриц. - просрочено, положит. - осталось
        (OPERATOR_GTE, 'Осталось/Просрочено дней >= Порога'),
        (OPERATOR_EQ, 'Осталось/Просрочено дней == Порогу'),
    ]

    name = models.CharField(max_length=100, verbose_name="Название правила (для админки)")
    days_threshold = models.IntegerField(
        verbose_name="Порог (дней)",
        help_text=(
            "Количество дней относительно СЕГОДНЯШНЕЙ ДАТЫ. "
            "Положительное: осталось N дней до срока. "
            "0: срок сегодня. "
            "Отрицательное: просрочено на N дней (например, -1 для 'просрочено на 1 день')."
        )
    )
    operator = models.CharField(
        max_length=10,
        choices=COMPARISON_OPERATOR_CHOICES,
        default=OPERATOR_LTE,
        verbose_name="Оператор сравнения для 'дней до срока'"
    )
    hex_color = models.CharField(
        max_length=7,
        validators=[RegexValidator(regex=r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$', message="Введите корректный HEX-код цвета (например, #RRGGBB)")],
        verbose_name="HEX-код цвета",
        default="#FFFFFF"
    )
    priority = models.PositiveIntegerField(
        default=10,
        verbose_name="Приоритет",
        help_text="Меньшее значение означает более высокий приоритет. Правила с одинаковым приоритетом применяются в порядке их ID."
    )
    is_active = models.BooleanField(default=True, verbose_name="Активно")

    class Meta:
        verbose_name = "Правило цвета для срока заказа"
        verbose_name_plural = "Правила цветов для сроков заказов"
        ordering = ['priority', 'id'] # Сначала по приоритету, потом по ID для стабильности

    def __str__(self):
        # Для наглядности в админке и логах
        # days_remaining_interpretation = f" (дней до срока {self.get_operator_display()} {self.days_threshold})"
        return f"{self.name} (Приоритет: {self.priority})"

    def check_condition(self, days_remaining_to_due_date):
        """
        Проверяет, соответствует ли количество дней до срока этому правилу.
        days_remaining_to_due_date:
            > 0: осталось дней до срока
            = 0: срок сегодня
            < 0: просрочено на abs(days_remaining_to_due_date) дней
        """
        if self.operator == self.OPERATOR_LTE:
            return days_remaining_to_due_date <= self.days_threshold
        elif self.operator == self.OPERATOR_GTE:
            return days_remaining_to_due_date >= self.days_threshold
        elif self.operator == self.OPERATOR_EQ:
            return days_remaining_to_due_date == self.days_threshold
        return False