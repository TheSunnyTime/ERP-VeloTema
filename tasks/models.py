# tasks/models.py
from django.db import models
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError # <--- ДОБАВИТЬ ИМПОРТ

# Импортируем модели из других приложений
from cash_register.models import CashRegister, ExpenseCategory, CashTransaction 
from suppliers.models import Supply


class TaskStatus(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Название статуса")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    is_final = models.BooleanField(default=False, verbose_name="Финальный статус (задача полностью закрыта)")
    order_in_list = models.PositiveIntegerField(default=0, verbose_name="Порядок для сортировки")

    class Meta:
        verbose_name = "Статус задачи"
        verbose_name_plural = "Статусы задач"
        ordering = ['order_in_list', 'name']

    def __str__(self):
        return self.name

class TaskType(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="Название типа задачи")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    default_visibility_groups = models.ManyToManyField(
        Group,
        blank=True,
        verbose_name="Группы с автоматической видимостью",
        help_text="Задачи этого типа будут автоматически видны пользователям из указанных групп"
    )

    class Meta:
        verbose_name = "Тип задачи"
        verbose_name_plural = "Типы задач"
        ordering = ['name']

    def __str__(self):
        return self.name

class Task(models.Model):
    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Низкий'),
        (PRIORITY_MEDIUM, 'Средний'),
        (PRIORITY_HIGH, 'Высокий'),
    ]

    title = models.CharField(max_length=255, verbose_name="Заголовок задачи")
    description = models.TextField(blank=True, null=True, verbose_name="Описание задачи")
    
    task_type = models.ForeignKey(
        TaskType, 
        on_delete=models.PROTECT,
        null=True, 
        blank=True,
        verbose_name="Тип задачи"
    )
    status = models.ForeignKey(
        TaskStatus, 
        on_delete=models.PROTECT,
        verbose_name="Статус задачи"
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM,
        verbose_name="Приоритет"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    due_date = models.DateTimeField(blank=True, null=True, verbose_name="Срок выполнения")
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата фактического выполнения")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_tasks',
        verbose_name="Автор задачи"
    )
    assigned_to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_tasks',
        verbose_name="Исполнитель (пользователь)"
    )
    assigned_to_group = models.ForeignKey(
        Group, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_group_tasks',
        verbose_name="Исполнитель (группа)"
    )

    content_type = models.ForeignKey(
        ContentType, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        verbose_name="Тип связанного объекта"
    )
    object_id = models.PositiveIntegerField(null=True, blank=True, verbose_name="ID связанного объекта")
    related_object = GenericForeignKey('content_type', 'object_id')

    payment_cash_register_for_supply = models.ForeignKey(
        CashRegister, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Касса для оплаты поставки",
        help_text="Заполняется для задач типа 'Оформить оплату поставки' перед переводом в статус 'Готово к выполнению'",
        limit_choices_to={'is_gko_for_supply_payment': True} 
    )

    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"
        ordering = ['-priority', '-created_at']

    def __str__(self):
        return self.title

    def clean(self):
        # Безопасный print для отладки
        status_name_for_print = 'Еще не установлен'
        if hasattr(self, 'status_id') and self.status_id: 
            try:
                if self.status: 
                    status_name_for_print = self.status.name
                else: 
                    status_name_for_print = TaskStatus.objects.get(pk=self.status_id).name
            except TaskStatus.DoesNotExist:
                status_name_for_print = f"ID {self.status_id} (не найден)"
        
        print(f"Вызван Task.clean() для объекта: {self.pk or 'Новый'}, статус попытки: {status_name_for_print}")

        super().clean()
        
        if not self.status_id or not self.task_type_id:
            return

        try:
            current_status_obj = TaskStatus.objects.get(pk=self.status_id)
            current_task_type_obj = TaskType.objects.get(pk=self.task_type_id)

            # Ключевые статусы и тип для проверок
            status_ready_for_processing = TaskStatus.objects.get(name="Готово к выполнению")
            task_type_supply_payment = TaskType.objects.get(name="Оформить оплату поставки")
            status_vyplnena = TaskStatus.objects.get(name="Выполнена") # Статус "Выполнена"
            status_oshibka_vypolneniya = TaskStatus.objects.get(name="Ошибка выполнения") # Статус "Ошибка выполнения"

        except (TaskStatus.DoesNotExist, TaskType.DoesNotExist) as e:
            print(f"WARNING (Task.clean): Не найдены один или несколько ключевых статусов/типов для валидации: {e}")
            return

        error_messages = [] # Собираем все ошибки валидации сюда

        # Блок 1: Валидация для перехода в "Готово к выполнению"
        if current_task_type_obj == task_type_supply_payment and current_status_obj == status_ready_for_processing:
            if not self.payment_cash_register_for_supply_id:
                error_messages.append(
                    ValidationError(
                        "Необходимо выбрать кассу для оплаты перед установкой статуса 'Готово к выполнению'.", 
                        code='missing_cash_register_for_supply_payment'
                    )
                )
            
            if not self.assigned_to_user_id and not self.assigned_to_group_id:
                error_messages.append(
                    ValidationError(
                        "Задача должна быть назначена исполнителю (пользователю или группе) перед установкой статуса 'Готово к выполнению'.", 
                        code='missing_assignee'
                    )
                )
        
        # Блок 2: Валидация на запрет ручной установки системных статусов "Выполнена" или "Ошибка выполнения"
        # для задач типа "Оформить оплату поставки"
        if current_task_type_obj == task_type_supply_payment:
            is_attempting_manual_system_status_set = False
            
            # Проверяем только для существующих задач (self.pk не None)
            if self.pk: 
                try:
                    old_task_instance = Task.objects.get(pk=self.pk)
                    old_status = old_task_instance.status # Статус до текущего изменения

                    # Если пытаются установить "Выполнена" или "Ошибка выполнения"
                    if current_status_obj == status_vyplnena or current_status_obj == status_oshibka_vypolneniya:
                        # И старый статус НЕ был "Готово к выполнению" (то есть это не системный переход)
                        # И старый статус НЕ был таким же, как текущий (т.е. статус действительно меняется на системный)
                        if old_status != status_ready_for_processing and old_status != current_status_obj:
                            is_attempting_manual_system_status_set = True
                
                except Task.DoesNotExist:
                    pass # Это новая задача, проверка не нужна

            # Если это новая задача, и ей сразу пытаются присвоить системный статус
            elif not self.pk and (current_status_obj == status_vyplnena or current_status_obj == status_oshibka_vypolneniya):
                 is_attempting_manual_system_status_set = True


            if is_attempting_manual_system_status_set:
                error_messages.append(
                    ValidationError(
                        f"Статус '{current_status_obj.name}' не может быть установлен вручную для этого типа задачи. Он устанавливается системой.",
                        code='manual_system_status_set'
                    )
                )

        if error_messages:
            raise ValidationError(error_messages)

    def _try_process_supply_payment(self, performing_user):
        # ... (код этого метода остается таким же, как в предыдущем сообщении)
        if not (self.related_object and isinstance(self.related_object, Supply)):
            print(f"INFO (Task {self.id}): Не связан объект Поставки или тип объекта некорректен для обработки платежа.")
            return False, "Не связан объект Поставки или тип объекта некорректен."

        supply_instance = self.related_object
        
        if supply_instance.payment_transaction_created:
            print(f"INFO (Task {self.id}): Оплата по поставке {supply_instance.id} уже была оформлена.")
            return True, "Оплата уже была оформлена." 

        if not self.payment_cash_register_for_supply: # Эта проверка здесь дублирует clean(), но оставим для надежности на уровне save()
            print(f"WARNING (Task {self.id}): Не выбрана касса для оплаты поставки {supply_instance.id} (вызов из _try_process_supply_payment).")
            return False, "Не выбрана касса для оплаты."

        try:
            expense_category = ExpenseCategory.objects.get(is_default_for_supply_payment=True)
            total_supply_cost = supply_instance.get_total_cost()

            if total_supply_cost <= 0:
                print(f"WARNING (Task {self.id}): Сумма поставки {supply_instance.id} равна нулю или отрицательна ({total_supply_cost}). Транзакция не создана.")
                return False, "Нулевая или отрицательная сумма поставки."
            
            payment_method_to_use = CashTransaction.PAYMENT_METHOD_CASH 
            if self.payment_cash_register_for_supply:
                if "безнал" in self.payment_cash_register_for_supply.name.lower() or \
                   "карт" in self.payment_cash_register_for_supply.name.lower():
                    payment_method_to_use = CashTransaction.PAYMENT_METHOD_TRANSFER
            
            CashTransaction.objects.create(
                cash_register=self.payment_cash_register_for_supply,
                transaction_type=CashTransaction.TRANSACTION_TYPE_EXPENSE,
                amount=total_supply_cost,
                expense_category=expense_category,
                description=f"Оплата по поставке №{supply_instance.id} (Задача №{self.id})",
                employee=performing_user, 
                payment_method=payment_method_to_use 
            )
            supply_instance.payment_transaction_created = True
            supply_instance.save(update_fields=['payment_transaction_created'])
            print(f"SUCCESS (Task {self.id}): Расходная операция по поставке №{supply_instance.id} успешно создана.")
            return True, f"Расходная операция по поставке №{supply_instance.id} успешно создана."

        except ExpenseCategory.DoesNotExist:
            msg = "Не найдена статья расходов по умолчанию для оплаты поставок."
            print(f"ERROR (Task {self.id}): {msg}")
            return False, msg
        except ExpenseCategory.MultipleObjectsReturned:
            msg = "Найдено несколько статей расходов по умолчанию для оплаты поставок."
            print(f"ERROR (Task {self.id}): {msg}")
            return False, msg
        except Exception as e:
            msg = f"Непредвиденная ошибка при создании кассовой транзакции: {e}"
            print(f"ERROR (Task {self.id}): {msg}")
            return False, msg

    def save(self, *args, **kwargs):
        # ... (код метода save остается таким же, как в предыдущем сообщении) ...
        old_status_id = None
        is_new_task = self._state.adding
        if not is_new_task:
            try:
                old_task_data = Task.objects.values('status_id').get(pk=self.pk)
                old_status_id = old_task_data['status_id']
            except Task.DoesNotExist:
                pass 

        performing_user = getattr(self, '_performing_user', self.assigned_to_user or self.created_by)
        
        # Вызываем clean() перед сохранением, если это не сохранение из fixture или что-то подобное
        if kwargs.get('force_insert', False) or kwargs.get('force_update', False) or kwargs.get('using', None):
             pass # Пропускаем clean для специфических случаев сохранения, где он может быть не нужен или вреден
        else:
            self.clean() # <--- ВЫЗОВ МЕТОДА CLEAN ПЕРЕД СОХРАНЕНИЕМ

        if is_new_task: 
            super().save(*args, **kwargs)

        try:
            task_type_supply_payment = TaskType.objects.get(name="Оформить оплату поставки") 
            status_ready_for_processing = TaskStatus.objects.get(name="Готово к выполнению")
            status_payment_done = TaskStatus.objects.get(name="Выполнена")
            status_processing_error = TaskStatus.objects.get(name="Ошибка выполнения")
        except (TaskType.DoesNotExist, TaskStatus.DoesNotExist) as e:
            print(f"CRITICAL ERROR (Task {self.id if self.id else 'New'}): Не найдены необходимые типы/статусы задач для обработки платежей: {e}")
            if not is_new_task: 
                super().save(*args, **kwargs)
            return 

        needs_processing = (
            self.task_type_id == task_type_supply_payment.id and # Сравниваем по ID
            self.status_id == status_ready_for_processing.id and 
            (is_new_task or (old_status_id is not None and old_status_id != status_ready_for_processing.id))
        )
        
        if needs_processing:
            success, message = self._try_process_supply_payment(performing_user)
            
            current_completed_at = self.completed_at 
            fields_to_update = []

            if success:
                if self.status_id != status_payment_done.id:
                    self.status = status_payment_done
                    fields_to_update.append('status')
                if not current_completed_at:
                    self.completed_at = timezone.now()
                    fields_to_update.append('completed_at')
                print(f"INFO (Task {self.id}): Статус обновлен на '{status_payment_done.name}'. {message}")
            else:
                if self.status_id != status_processing_error.id:
                    self.status = status_processing_error
                    fields_to_update.append('status')
                print(f"WARNING (Task {self.id}): Статус обновлен на '{status_processing_error.name}'. Причина: {message}")
            
            if fields_to_update:
                super().save(update_fields=fields_to_update)
            elif not is_new_task: 
                super().save(*args, **kwargs)
        
        elif self.status and self.status.is_final and not self.completed_at and \
             (is_new_task or (old_status_id is not None and old_status_id != self.status_id)):
            self.completed_at = timezone.now()
            super().save(update_fields=['completed_at', 'status'] if old_status_id != self.status_id else ['completed_at'])
        elif not is_new_task: 
            super().save(*args, **kwargs)