# CRM 2.0/ERP/clients/models.py
from django.db import models
from django.conf import settings
from products.models import Product

class ClientGroup(models.Model):
    name = models.CharField(
        max_length=150,
        unique=True,
        verbose_name="Название группы клиентов"
    )

    class Meta:
        verbose_name = "Группа клиентов"
        verbose_name_plural = "Группы клиентов"

    def __str__(self):
        return self.name

class Client(models.Model):
    name = models.CharField(
        max_length=255,
        verbose_name="ФИО или Название компании клиента"
    )
    #phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Номер телефона") # <--- ДОБАВЬ ЭТО ПОЛЕ
    contact_person = models.CharField(
        max_length=255,
        blank=True, null=True,
        verbose_name="Контактное лицо"
    )
    phone = models.CharField(
        max_length=50,
        blank=True, null=True,
        verbose_name="Телефон"
    )
    email = models.EmailField(
        max_length=254, # Стандартная максимальная длина для email
        blank=True, null=True,
        unique=True, # Email должен быть уникальным, если указан
        verbose_name="Email"
    )
    address = models.TextField(
        blank=True, null=True,
        verbose_name="Адрес"
    )
    client_group = models.ForeignKey(
        ClientGroup,
        on_delete=models.SET_NULL, # Если группу удалят, у клиента это поле станет пустым
        null=True,                 # Разрешаем полю быть пустым
        blank=True,                # Поле может быть не заполнено в формах
        related_name='clients',
        verbose_name="Группа клиентов"
    )
    
    notes = models.TextField(
        blank=True, null=True,
        verbose_name="Примечания о клиенте"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")

    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"
        ordering = ['name'] # Сортировка по умолчанию

    def __str__(self):
        return self.name
    