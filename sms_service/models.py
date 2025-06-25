from django.db import models

# Create your models here.
# F:\CRM 2.0\ERP\sms_service\models.py

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class SMSSettings(models.Model):
    """
    Настройки для подключения к Rocket SMS
    Здесь храним логин, пароль и настройки API
    """
    
    name = models.CharField(
        max_length=100,
        default="Rocket SMS",
        verbose_name="Название настройки"
    )
    
    # API настройки Rocket SMS
    username = models.CharField(
        max_length=100,
        verbose_name="Логин Rocket SMS"
    )
    
    password = models.CharField(
        max_length=100,
        verbose_name="Пароль Rocket SMS"
    )
    
    # URL API (обычно не меняется)
    api_url = models.URLField(
    verbose_name="URL API",
    default="http://api.rocketsms.by",
    help_text="URL для отправки запросов к API Rocket SMS"
)
    
    # Имя отправителя (показывается клиентам)
    sender_name = models.CharField(
        max_length=15,
        default="VeloTema",
        verbose_name="Имя отправителя"
    )
    
    # Активные настройки или нет
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активные настройки"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")
    
    class Meta:
        verbose_name = "Настройки SMS"
        verbose_name_plural = "Настройки SMS"
    
    def __str__(self):
        return f"{self.name} ({'Активно' if self.is_active else 'Неактивно'})"
    

class SMSTemplate(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название шаблона")
    
    # Добавляем код шаблона для удобного обращения из кода
    template_code = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name="Код шаблона",
        help_text="Уникальный код для использования в коде (например: new_order_repair)"
    )
    
    # Обновляем типы шаблонов с учетом типов заказов
    template_type = models.CharField(
        max_length=50,
        choices=[
            ('new_order_repair', 'Новый заказ - Ремонт'),
            ('new_order_sale', 'Новый заказ - Продажа'),
            ('order_completed', 'Заказ выполнен'),
            ('order_ready', 'Заказ готов к выдаче'),
            ('meeting_reminder', 'Напоминание о встрече'),
            ('payment_reminder', 'Напоминание об оплате'),
        ],
        verbose_name="Тип шаблона"
    )
    
    message_text = models.TextField(
        verbose_name="Текст сообщения",
        help_text="Можно использовать переменные: {client_name}, {order_number}, {order_type}, {total_amount}, {due_date}, {product_name}"
    )
    
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    
    class Meta:
        verbose_name = "Шаблон SMS"
        verbose_name_plural = "Шаблоны SMS"
        ordering = ['template_type', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.template_code})"
    
    # Заменяем переменные в тексте на реальные данные
    def get_message_with_variables(self, client_name="", order_id="", status=""):
        """
        Заменяет переменные в шаблоне на реальные данные
        """
        message = self.message_text
        message = message.replace("{client_name}", str(client_name))
        message = message.replace("{order_id}", str(order_id))
        message = message.replace("{status}", str(status))
        return message
    

class SMSCampaign(models.Model):
    """
    SMS рассылка - группа сообщений отправленных одновременно
    """
    
    name = models.CharField(
        max_length=200,
        verbose_name="Название рассылки"
    )
    
    # Какой шаблон используем
    template = models.ForeignKey(
        SMSTemplate,
        on_delete=models.CASCADE,
        verbose_name="Шаблон сообщения"
    )
    
    # Кому отправляем
    RECIPIENT_TYPES = [
        ('all_clients', 'Всем клиентам'),
        ('active_orders', 'Клиенты с активными заказами'),
        ('manual_list', 'Ручной список номеров'),
    ]
    
    recipient_type = models.CharField(
        max_length=20,
        choices=RECIPIENT_TYPES,
        default='manual_list',
        verbose_name="Кому отправить"
    )
    
    # Для ручного списка номеров
    manual_phone_numbers = models.TextField(
        blank=True,
        null=True,
        verbose_name="Номера телефонов",
        help_text="Вводи номера через запятую. Пример: +375291234567, +375293334455"
    )
    
    # Статус рассылки
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('scheduled', 'Запланирована'),
        ('sending', 'Отправляется'),
        ('sent', 'Отправлена'),
        ('failed', 'Ошибка'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name="Статус"
    )
    
    # Когда отправить (можно запланировать на будущее)
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Запланировано на"
    )
    
    # Кто создал рассылку
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Создал"
    )
    
    # Счётчики
    total_messages = models.IntegerField(
        default=0,
        verbose_name="Всего сообщений"
    )
    
    sent_messages = models.IntegerField(
        default=0,
        verbose_name="Отправлено"
    )
    
    failed_messages = models.IntegerField(
        default=0,
        verbose_name="Не отправлено"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлена")
    
    class Meta:
        verbose_name = "SMS рассылка"
        verbose_name_plural = "SMS рассылки"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    

class SMSMessage(models.Model):
    """
    История отправленных SMS сообщений
    Каждое отдельное SMS сообщение
    """
    
    # К какой рассылке относится (может быть пустым для одиночных SMS)
    campaign = models.ForeignKey(
        SMSCampaign,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='messages',
        verbose_name="Рассылка"
    )
    
    # Номер телефона получателя
    phone_number = models.CharField(
        max_length=20,
        verbose_name="Номер телефона"
    )
    
    # Имя получателя (если известно)
    recipient_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Имя получателя"
    )
    
    # Текст отправленного сообщения
    message_text = models.TextField(
        verbose_name="Текст сообщения"
    )
    
    # Статус отправки
    STATUS_CHOICES = [
        ('pending', 'Ожидает отправки'),
        ('sent', 'Отправлено'),
        ('delivered', 'Доставлено'),
        ('failed', 'Ошибка'),
        ('rejected', 'Отклонено'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Статус"
    )
    
    # ID сообщения от Rocket SMS (для отслеживания)
    rocket_sms_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="ID в Rocket SMS"
    )
    
    # Ответ от Rocket SMS API
    api_response = models.TextField(
        blank=True,
        null=True,
        verbose_name="Ответ API"
    )
    
    # Стоимость SMS
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Стоимость"
    )
    
    # Кто отправил
    sent_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Отправил"
    )
    
    # Даты
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Отправлено")
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="Доставлено")
    
    class Meta:
        verbose_name = "SMS сообщение"
        verbose_name_plural = "SMS сообщения"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"SMS для {self.phone_number} ({self.get_status_display()})"