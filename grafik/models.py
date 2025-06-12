import calendar
from django.db import models
from django.contrib.auth.models import User, Group
from django.conf import settings
from datetime import timedelta  # <--- ДОБАВЬ этот импорт!

# Приложение: grafik

class Shift(models.Model):
    """Модель для хранения рабочих смен сотрудников."""
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
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
        unique_together = ('employee', 'date', 'start_time')
        ordering = ['date', 'start_time']

    def __str__(self):
        return f"Смена: {self.employee.get_full_name() or self.employee.username} - {self.date.strftime('%d.%m.%Y')} ({self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')})"

    @property
    def duration(self):
        """Возвращает продолжительность смены в часах (приблизительно)."""
        if self.start_time and self.end_time:
            from datetime import datetime, date as dt_date
            dummy_date = dt_date.today()
            start_dt = datetime.combine(dummy_date, self.start_time)
            end_dt = datetime.combine(dummy_date, self.end_time)
            if end_dt < start_dt:
                end_dt += timedelta(days=1)
            duration_timedelta = end_dt - start_dt
            return duration_timedelta.total_seconds() / 3600
        return 0

# --- ДОБАВЛЯЕМ Модель шаблона расписания ---
class ScheduleTemplate(models.Model):
    """Шаблон расписания для сотрудника"""
    employee = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Сотрудник"
    )
    work_days = models.CharField(
        max_length=20,
        verbose_name="Рабочие дни недели",
        help_text="Через запятую: 0 - Пн, 1 - Вт, 2 - Ср, 3 - Чт, 4 - Пт, 5 - Сб, 6 - Вс. Например: 0,1,2,3,4"
    )
    start_time = models.TimeField(verbose_name="Время начала")
    end_time = models.TimeField(verbose_name="Время окончания")

    def get_work_days_list(self):
        return [int(d) for d in self.work_days.split(",") if d.strip().isdigit()]

    def __str__(self):
        return f"Шаблон: {self.employee.get_full_name() or self.employee.username}"

    class Meta:
        verbose_name = "Шаблон расписания"
        verbose_name_plural = "Шаблоны расписаний"

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
    DAY_OF_WEEK_CHOICES = [(i, calendar.day_name[i]) for i in range(7)]  # 0=Понедельник, ..., 6=Воскресенье

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
    assigned_employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Конкретный сотрудник",
        help_text="Если указано, правило применяется только к этому сотруднику."
    )
    assigned_group = models.ForeignKey(
        Group,
        null=True, blank=True,
        on_delete=models.SET_NULL,
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
    applies_to_workday = models.BooleanField(
        null=True, blank=True,
        verbose_name="Применять к рабочему/выходному дню?",
        help_text="Да - применяется к дню, когда у сотрудника есть смена. Нет - к дню, когда смены нет. Пусто - не учитывать этот критерий."
    )
    is_active = models.BooleanField(default=True, verbose_name="Правило активно?")

    class Meta:
        verbose_name = "Правило назначения цвета"
        verbose_name_plural = "Правила назначения цветов"
        ordering = ['-priority', 'name']

    def __str__(self):
        return f"{self.name} (Приоритет: {self.priority}, Цвет: {self.color_to_apply.name})"