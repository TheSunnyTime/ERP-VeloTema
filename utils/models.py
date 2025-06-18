# F:\CRM 2.0\ERP\utils\models.py
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group
from django.conf import settings # Был нужен для зарплатных моделей, теперь может быть не нужен здесь
from django.utils import timezone # Был нужен для зарплатных моделей, теперь может быть не нужен здесь
# Импортируем модель заметок из отдельного файла
from .notes.models import ServiceNote

# Делаем модель доступной в админке utils
__all__ = ['ServiceNote']

# Импорты моделей из других приложений ForeignKey больше не нужны здесь, если они использовались только для зарплатных моделей
# from orders.models import OrderType, Order, OrderServiceItem

# --- Существующие модели, которые ОСТАЮТСЯ в utils ---

class ProductPriceImporter(models.Model):
    class Meta:
        managed = False
        verbose_name = "Импорт прайс-листа товаров"
        verbose_name_plural = "Импорт прайс-листа товаров"
        permissions = [
            ("can_import_product_prices", "Может импортировать прайс-листы товаров"),
        ]
    def __str__(self):
        return self.Meta.verbose_name

class DocumentType(models.Model):
    name = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="Название типа документа"
    )
    related_model = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name="Связанная модель (основной источник данных)",
        help_text="Выберите модель, данные из которой будут в основном использоваться в этом типе документа (например, 'Заказ')."
    )
    placeholders_hint = models.TextField(
        blank=True,
        verbose_name="Подсказка по доступным плейсхолдерам",
        help_text=("Опишите здесь основные плейсхолдеры, доступные для этого типа документа. "
                   "Например: #Номер_Заказа#, #Дата_Заказа#, #Клиент_Имя# и т.д. "
                   "Для списков: #СписокТоваров_Начало# ... #Поз_Название# ... #СписокТоваров_Конец#")
    )

    class Meta:
        verbose_name = "Тип документа"
        verbose_name_plural = "Типы документов"
        ordering = ['name']

    def __str__(self):
        return self.name

class DocumentTemplate(models.Model):
    name = models.CharField(
        max_length=255,
        verbose_name="Название шаблона"
    )
    document_type = models.ForeignKey(
        DocumentType, 
        on_delete=models.PROTECT,
        related_name='templates',
        verbose_name="Тип документа"
    )
    template_content = models.TextField(
        verbose_name="Содержимое шаблона (HTML с плейсхолдерами)",
        help_text="Используйте текст и плейсхолдеры вида #ИМЯ_ПЛЕЙСХОЛДЕРА#. Список доступных плейсхолдеров см. в описании выбранного Типа документа. Можно использовать базовые HTML теги для форматирования (например, < b >, < i >, < p >, < br >, таблицы)."
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен (доступен для генерации)"
    )
    allowed_editing_groups = models.ManyToManyField(
        Group,
        blank=True,
        verbose_name="Группы с правом редактирования этого шаблона"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Шаблон документа"
        verbose_name_plural = "Шаблоны документов"
        ordering = ['document_type', 'name']
        unique_together = ('document_type', 'name')

    def __str__(self):
        return f"{self.name} ({self.document_type.name})"

class ExportStockLevelsTool(models.Model):
    class Meta:
        # verbose_name и verbose_name_plural будут отображаться в админке
        verbose_name = "Инструмент: Выгрузка остатков" 
        verbose_name_plural = "Инструменты: Выгрузка остатков"
        app_label = 'utils'  # Указываем, к какому приложению относится модель
        managed = False      # ВАЖНО: Django не будет управлять таблицей этой модели в БД
                             # (т.е. не будет создавать, изменять, удалять ее)
# --- Модели для Зарплаты УДАЛЕНЫ ОТСЮДА ---
# EmployeeRate, SalaryCalculation, SalaryCalculationDetail, SalaryPayment
# теперь будут в salary_management/models.py

class ImportSupplyItemsTool(models.Model): # Наша новая модель для ссылки
    class Meta:
        verbose_name = "Инструмент: Импорт позиций Поставки (CSV)" 
        verbose_name_plural = "Инструменты: Импорт позиций Поставки (CSV)"
        app_label = 'utils'  # Привязываем к приложению utils
        managed = False      # Таблица в БД создаваться не будет