# CRM 2.0/ERP/clients/models.py
import re # Модуль для регулярных выражений
from django.db import models
from django.conf import settings # Не используется здесь напрямую, но может быть в других частях
# from products.models import Product # Не используется в этих моделях, можно убрать если не нужно для другого
from django.core.exceptions import ValidationError

class ClientGroup(models.Model):
    name = models.CharField(
        max_length=150,
        unique=True,
        verbose_name="Название группы клиентов"
    )
    description = models.TextField(blank=True, null=True, verbose_name="Описание") # Добавил поле description для полноты

    class Meta:
        verbose_name = "Группа клиентов"
        verbose_name_plural = "Группы клиентов"
        ordering = ['name'] # Добавил сортировку

    def __str__(self):
        return self.name

class Client(models.Model):
    name = models.CharField(
        max_length=255,
        verbose_name="ФИО или Название компании клиента"
    )
    contact_person = models.CharField(
        max_length=255,
        blank=True, null=True, # Оставляем опциональным
        verbose_name="Контактное лицо"
    )
    phone = models.CharField(
        max_length=25,  # Достаточно для хранения очищенных цифр или с маской до очистки
        unique=True,    # Гарантирует уникальность на уровне БД (после очистки)
        blank=True,     # Разрешаем пустое значение, если телефон не обязателен
        null=True,      # Разрешаем NULL в БД, если телефон не указан
        verbose_name="Телефон",
        help_text="Введите номер в формате +375 (XX) XXX-XX-XX. Будет сохранен только в цифровом виде."
    )
    email = models.EmailField(
        max_length=254, 
        blank=True, null=True,
        unique=True, # Email должен быть уникальным, если указан, иначе null=True это разрешает
        verbose_name="Email"
    )
    address = models.TextField(
        blank=True, null=True,
        verbose_name="Адрес"
    )
    client_group = models.ForeignKey(
        ClientGroup,
        on_delete=models.SET_NULL, 
        null=True,                 
        blank=True,                
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
        ordering = ['name'] 

    def __str__(self):
        return self.name

    def _clean_phone_number(self, phone_number_str):
        """Вспомогательный метод для очистки и базовой нормализации номера."""
        if not phone_number_str:
            return None
        
        # Удаляем все, кроме цифр
        cleaned_phone = re.sub(r'\D', '', phone_number_str)

        if not cleaned_phone: # Если после очистки ничего не осталось
            return None
            
        # Приводим к единому формату (например, 375XXXXXXXXX)
        if len(cleaned_phone) == 9 and not cleaned_phone.startswith("375"): # Например, 251234567
            cleaned_phone = "375" + cleaned_phone
        elif len(cleaned_phone) == 10 and cleaned_phone.startswith("80"): # Например, 80251234567
            cleaned_phone = "375" + cleaned_phone[2:]
        # Можно добавить другие правила нормализации, если нужно

        return cleaned_phone

    def clean(self):
        """
        Кастомная валидация на уровне модели.
        """
        super().clean()
        
        if self.phone:
            original_phone_for_validation = self.phone # Сохраняем для сравнения, если очистка не нужна
            cleaned_phone = self._clean_phone_number(self.phone)

            if cleaned_phone is None and original_phone_for_validation.strip() != "":
                # Если ввели что-то, что полностью стерлось (например, "abc-def")
                # и телефон не обязателен, то self.phone станет None.
                # Если телефон обязателен (blank=False), то это вызовет ошибку на уровне формы.
                # Здесь мы просто присваиваем None, если после очистки пусто.
                self.phone = None
            elif cleaned_phone:
                # Валидация длины и формата для белорусских номеров
                if cleaned_phone.startswith("375") and len(cleaned_phone) != 12:
                    raise ValidationError({
                        'phone': f"Некорректная длина белорусского номера. Ожидается 12 цифр (включая 375), получено {len(cleaned_phone)} для '{original_phone_for_validation}'."
                    })
                # Можно добавить другие правила валидации для не-белорусских номеров, если они допустимы
                # elif not cleaned_phone.startswith("375"):
                #    pass # или raise ValidationError

                self.phone = cleaned_phone # Присваиваем очищенный и нормализованный номер

        # Валидация уникальности email, если он указан (учитывая, что null=True)
        if self.email:
            qs = Client.objects.filter(email__iexact=self.email) # Регистронезависимая проверка
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({'email': 'Клиент с таким Email уже существует.'})


    def save(self, *args, **kwargs):
        # Вызов full_clean() здесь обеспечит выполнение метода clean() и валидаторов модели
        # перед сохранением, даже если объект сохраняется не через ModelForm.
        # Это важно для консистентности данных.
        # Однако, ModelAdmin уже вызывает full_clean() для формы.
        # Если ты хочешь быть абсолютно уверенным, можно раскомментировать, но это может быть излишне.
        # self.full_clean() # Раскомментировать, если есть сценарии сохранения объекта напрямую, минуя формы.
        
        # Очистка телефона перед сохранением (на случай, если clean не вызывался или для полной уверенности)
        # Эта логика дублирует часть из clean(), но гарантирует, что в БД попадет очищенный номер.
        if self.phone:
            self.phone = self._clean_phone_number(self.phone)
            if self.phone is None and self._meta.get_field('phone').blank is False:
                 # Это не должно произойти, если blank=False, т.к. форма/модель должны были выдать ошибку раньше
                 # Но на всякий случай, если телефон обязателен, а стал None после очистки.
                 raise ValidationError("Поле 'Телефон' не может быть пустым после очистки.")


        super().save(*args, **kwargs)