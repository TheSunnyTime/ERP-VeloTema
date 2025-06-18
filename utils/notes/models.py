# F:\CRM 2.0\ERP\utils\notes\models.py

from django.db import models
from django.conf import settings

class ServiceNote(models.Model):
    """
    Служебные заметки для админов
    Хранит важную информацию о функциях системы
    """
    
    title = models.CharField(
        max_length=200,
        verbose_name="Заголовок заметки"
    )
    
    content = models.TextField(
        verbose_name="Содержание заметки",
        help_text="Подробное описание функции или инструкция"
    )
    
    category = models.CharField(
        max_length=50,
        choices=[
            ('export', 'Экспорт данных'),
            ('import', 'Импорт данных'),
            ('api', 'API и интеграции'),
            ('reports', 'Отчёты'),
            ('settings', 'Настройки'),
            ('other', 'Прочее'),
        ],
        default='other',
        verbose_name="Категория"
    )
    
    # УБИРАЕМ ЗАПЯТУЮ после is_important
    is_important = models.BooleanField(
        default=False,
        verbose_name="Важная заметка",
        help_text="Отметить как важную (будет выделена)"
    )

    # УБИРАЕМ ЗАПЯТУЮ после is_admin_only
    is_admin_only = models.BooleanField(
        default=False,
        verbose_name="Только для администрации",
        help_text="Эту заметку смогут видеть только пользователи из группы 'Администраторы'"
    )
    
    # ДОБАВЛЯЕМ поле created_by
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Создал",
        help_text="Пользователь, который создал заметку",
        null=True,
        blank=True
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата изменения"
    )

    class Meta:
        verbose_name = "Служебная заметка"
        verbose_name_plural = "Служебные заметки"
        ordering = ['-created_at']
        app_label = 'utils'

    def __str__(self):
        return self.title