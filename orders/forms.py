# F:\CRM 2.0\ERP\orders\forms.py
from django import forms
from django.core.exceptions import ValidationError
from .models import Order, OrderType # Убедись, что OrderType импортирован

# Если в BaseOrderProductItemFormSet используется модель Product, ее нужно импортировать:
# from products.models import Product

class BaseOrderProductItemFormSet(forms.BaseInlineFormSet):
    # ... (твой существующий код)
    # Пример:
    # def clean(self):
    #     super().clean()
    #     # какая-то логика, если нужна
    pass


# --- ФОРМА ДЛЯ OrderAdmin ---
class OrderAdminForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = '__all__' # Админка сама будет управлять отображением полей через fieldsets

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = self.instance

        # Логика определения is_repair_type и current_status
        # (оставлена как в твоем коде, предполагает, что OrderType.TYPE_REPAIR определена в модели OrderType)
        is_repair_type = False
        current_status = None

        if instance and instance.pk and instance.order_type:
            if instance.order_type.name == OrderType.TYPE_REPAIR: # Используем константу из модели OrderType
                is_repair_type = True
        # Проверка self.data (отправленные данные формы)
        elif self.data and 'order_type' in self.data:
            try:
                order_type_id = self.data.get('order_type')
                if order_type_id: # Убедимся, что ID не пустой
                    order_type_obj = OrderType.objects.get(pk=order_type_id)
                    if order_type_obj.name == OrderType.TYPE_REPAIR:
                        is_repair_type = True
            except (OrderType.DoesNotExist, ValueError, TypeError): # Добавлен TypeError на случай если order_type_id невалиден для pk
                pass
        # Проверка self.initial (начальные данные для новой формы)
        elif self.initial.get('order_type'):
            try:
                initial_order_type_id = self.initial.get('order_type')
                if initial_order_type_id: # Убедимся, что ID не пустой
                    order_type_obj = OrderType.objects.get(pk=initial_order_type_id)
                    if order_type_obj.name == OrderType.TYPE_REPAIR:
                        is_repair_type = True
            except (OrderType.DoesNotExist, ValueError, TypeError):
                pass

        # Определение текущего статуса
        if instance and instance.pk and instance.status:
            current_status = instance.status
        elif self.data and 'status' in self.data:
            current_status = self.data.get('status')
        elif self.initial.get('status'):
            current_status = self.initial.get('status')
        else: # Для нового заказа, если статус не передан, по умолчанию 'new'
            current_status = Order.STATUS_NEW


        if 'performer' in self.fields:
            # Всегда устанавливаем required=False для поля формы,
            # чтобы избежать стандартной ошибки Django "Это поле обязательно.".
            # Наша основная валидация (с кастомным сообщением) будет в Order.clean().
            # JavaScript отвечает за визуальное отображение обязательности (звездочка, HTML required).
            self.fields['performer'].required = False

            # Опционально: можно добавить CSS-класс для стилизации, если JS этого не делает
            # или если нужно специальное отображение при серверной ошибке.
            # if is_repair_type and current_status and current_status != Order.STATUS_NEW:
            #     self.fields['performer'].widget.attrs.update({'class': 'conditionally-required-by-server'})


    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        payment_method = cleaned_data.get('payment_method_on_closure')
        # order_type и performer здесь не используются для валидации исполнителя,
        # так как эта логика перенесена в Order.clean() для централизации.

        is_new_object = not self.instance or not self.instance.pk

        # Валидация: Новый заказ не может быть сразу "Выдан"
        if is_new_object and status == Order.STATUS_ISSUED:
            raise ValidationError(
                "Новый заказ не может быть сразу создан со статусом 'Выдан'. "
                "Сначала сохраните заказ (например, со статусом 'Новый'), добавьте позиции, "
                "затем укажите метод оплаты и измените статус на 'Выдан'."
            ) # Эта ошибка будет не-полевой (non-field error)

        # Валидация: Если статус "Выдан", метод оплаты должен быть указан
        if status == Order.STATUS_ISSUED and not payment_method:
            self.add_error('payment_method_on_closure',
                           ValidationError("Метод оплаты должен быть указан, если статус заказа 'Выдан'.",
                                           code='payment_method_required_for_issue'))

        # Валидация для обязательности исполнителя (тип "Ремонт", статус не "Новый")
        # теперь ПОЛНОСТЬЮ находится в Order.clean() в models.py.
        # Это обеспечивает, что валидация происходит на уровне модели и сообщение об ошибке
        # генерируется там (и должно быть привязано к полю 'performer' через словарь).
        # Поэтому здесь мы не дублируем эту логику.

        return cleaned_data