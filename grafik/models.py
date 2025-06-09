import calendar # Для choices в day_of_week
from django.db import models
from django.contrib.auth.models import User, Group
from django.conf import settings # Если User = settings.AUTH_USER_MODEL

# Приложение: grafik

class Shift(models.Model):
    """Модель для хранения рабочих смен сотрудников."""
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL, # Используем стандартную модель пользователя Django
        on_delete=models.CASCADE, 
        verbose_name="Сотрудник"
    )
    date = models.DateField(verbose_name="Дата")
    start_time = models.TimeField(verbose_name="Время начала")
    end_time = models.TimeField(verbose_name="Время окончания")
    notes = models.TextField(blank=True, null=True, verbose_name="Примечания")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Смена"
        verbose_name_plural = "Смены"
        # Уникальность смены для сотрудника на дату и время начала.
        # Можно также добавить валидацию на пересечение временных интервалов на уровне формы/модели.
        unique_together = ('employee', 'date', 'start_time')
        ordering = ['date', 'start_time']
        # Права доступа будут управляться стандартными Django permissions
        # (например, grafik.add_shift, grafik.change_shift и т.д.)

    def __str__(self):
        return f"Смена: {self.employee.get_full_name() or self.employee.username} - {self.date.strftime('%d.%m.%Y')} ({self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')})"

    @property
    def duration(self):
        """Возвращает продолжительность смены в часах (приблизительно)."""
        if self.start_time and self.end_time:
            # Для расчета точной продолжительности нужно будет преобразовать time в datetime с одной датой
            # Это упрощенный вариант, который может неверно работать для смен через полночь (пока не предполагаем)
            from datetime import datetime, date as dt_date
            dummy_date = dt_date.today() # Используем любую дату, т.к. важна только разница во времени
            start_dt = datetime.combine(dummy_date, self.start_time)
            end_dt = datetime.combine(dummy_date, self.end_time)
            if end_dt < start_dt: # Если смена переходит через полночь (например, 22:00 - 02:00)
                end_dt += timedelta(days=1) # Добавляем день к конечной дате
            
            duration_timedelta = end_dt - start_dt
            return duration_timedelta.total_seconds() / 3600  # в часах
        return 0

class ColorRule(models.Model):
    """Модель для определения конкретных цветов."""
    name = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name="Название правила цвета",
        help_text="Например, 'Рабочий день исполнителя', 'Выходной день'"
    )
    hex_color = models.CharField(
        max_length=7, 
        verbose_name="HEX-код цвета",
        help_text="Например, #RRGGBB или #RGB"
    )
    description = models.TextField(blank=True, null=True, verbose_name="Описание")

    class Meta:
        verbose_name = "Правило цвета"
        verbose_name_plural = "Правила цветов"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.hex_color})"

class ColorAssignment(models.Model):
    """
    Модель для определения условий, при которых применяется правило цвета.
    Определяет, какой цвет (ColorRule) будет назначен на основе различных условий.
    """
    # Генерация choices для дней недели
    DAY_OF_WEEK_CHOICES = [(i, calendar.day_name[i]) for i in range(7)] # 0=Понедельник, ..., 6=Воскресенье

    name = models.CharField(
        max_length=255, 
        verbose_name="Название условия назначения",
        help_text="Например, 'Цвет для рабочих смен исполнителей', 'Цвет для суббот'"
    )
    color_to_apply = models.ForeignKey(
        ColorRule, 
        on_delete=models.CASCADE, 
        verbose_name="Применяемый цвет"
    )
    priority = models.IntegerField(
        default=0, 
        verbose_name="Приоритет",
        help_text="Чем выше значение (например, 100), тем выше приоритет правила. Правила с более высоким приоритетом перекрывают правила с более низким."
    )
    
    # --- Условия применения ---
    # Эти поля опциональны. Если поле не заполнено, оно не учитывается при проверке условия.
    
    assigned_employee = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, blank=True, 
        on_delete=models.SET_NULL, # Если юзер удален, правило может остаться (или CASCADE?)
        verbose_name="Конкретный сотрудник",
        help_text="Если указано, правило применяется только к этому сотруднику."
    )
    assigned_group = models.ForeignKey(
        Group, 
        null=True, blank=True, 
        on_delete=models.SET_NULL, # Если группа удалена
        verbose_name="Группа сотрудников",
        help_text="Если указано, правило применяется к сотрудникам из этой группы (игнорируется, если указан 'Конкретный сотрудник')."
    )
    day_of_week = models.IntegerField(
        choices=DAY_OF_WEEK_CHOICES, 
        null=True, blank=True, 
        verbose_name="День недели",
        help_text="Если указано, правило применяется только к этому дню недели."
    )
    specific_date = models.DateField(
        null=True, blank=True, 
        verbose_name="Конкретная дата",
        help_text="Если указано, правило применяется только к этой дате (например, для праздников)."
    )
    # is_holiday - можно будет реализовать через specific_date или отдельную модель Holiday в будущем
    
    applies_to_workday = models.BooleanField(
        null=True, blank=True, # Используем BooleanField с null=True, чтобы иметь три состояния
        verbose_name="Применять к рабочему/выходному дню?",
        help_text="Да - применяется к дню, когда у сотрудника есть смена. Нет - к дню, когда смены нет. Пусто - не учитывать этот критерий."
    )
    
    is_active = models.BooleanField(default=True, verbose_name="Правило активно?")

    class Meta:
        verbose_name = "Правило назначения цвета"
        verbose_name_plural = "Правила назначения цветов"
        ordering = ['-priority', 'name'] # Сначала самые приоритетные

    def __str__(self):
        return f"{self.name} (Приоритет: {self.priority}, Цвет: {self.color_to_apply.name})"