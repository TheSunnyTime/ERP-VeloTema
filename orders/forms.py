# F:\CRM 2.0\ERP\orders\forms.py
from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal # Убедимся, что Decimal импортирован, если будем использовать для суммы
from .models import Order, OrderType 

# Если в BaseOrderProductItemFormSet используется модель Product, ее нужно импортировать:
# from products.models import Product

class BaseOrderProductItemFormSet(forms.BaseInlineFormSet):
    # Оставляем твой существующий код здесь, если он есть
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
        # Твоя существующая логика __init__ для performer.required = False остается.
        # Это правильно, чтобы стандартная HTML5 валидация не срабатывала раньше нашей.
        if 'performer' in self.fields:
            self.fields['performer'].required = False


    def clean(self):
        cleaned_data = super().clean()
        
        status = cleaned_data.get('status')
        order_type = cleaned_data.get('order_type') 
        performer = cleaned_data.get('performer')   
        payment_method_on_closure = cleaned_data.get('payment_method_on_closure')

        is_new_object = not self.instance or not self.instance.pk

        # Валидация: Новый заказ не может быть сразу "Выдан"
        if is_new_object and status == Order.STATUS_ISSUED:
            self.add_error('status', ValidationError(
                "Новый заказ не может быть сразу создан со статусом 'Выдан'. "
                "Пожалуйста, выберите другой начальный статус."
            ))
            # Если эта ошибка возникла, дальнейшие проверки для статуса "Выдан" могут быть излишни
            # или могут вызвать путаницу, поэтому можно вернуть cleaned_data раньше,
            # но Django обработает несколько ошибок для одного поля нормально.

        # Валидации, специфичные для статуса "Выдан"
        if status == Order.STATUS_ISSUED:
            # 1. Проверка метода оплаты
            if not payment_method_on_closure:
                self.add_error('payment_method_on_closure',
                               ValidationError("Метод оплаты должен быть указан, если статус заказа 'Выдан'.",
                                               code='payment_method_required_for_issue'))

            # 2. Проверка исполнителя для типа "Ремонт"
            if order_type and order_type.name == OrderType.TYPE_REPAIR and not performer:
                self.add_error('performer', 
                               ValidationError(f"Исполнитель должен быть указан для типа заказа '{OrderType.TYPE_REPAIR}' "
                                               f"при установке статуса 'Выдан'.",
                                               code='performer_required_for_repair_issue'))
            
            # 3. Проверка общей суммы заказа (оставляем в save_related из-за зависимости от инлайнов)
            # Если бы мы хотели ее здесь (с ограничениями):
            # if self.instance and self.instance.pk: # Только для существующих заказов
            #     # ВНИМАНИЕ: Эта сумма будет на основе данных ДО сохранения текущих изменений в инлайнах
            #     current_order_total_before_inline_save = self.instance.calculate_total_amount()
            #     if not (current_order_total_before_inline_save > Decimal('0.00')):
            #         self.add_error(None, # Общая ошибка формы
            #                        f"Сумма заказа ({current_order_total_before_inline_save}) должна быть > 0 для выдачи. "
            #                        f"Примечание: Проверка суммы на этом этапе не учитывает несохраненные изменения в товарах/услугах.")
        
        # Валидация для обязательности исполнителя для типа "Ремонт", если статус НЕ "Новый" и НЕ "Выдан"
        # Эта логика также есть в Order.clean() модели. Наличие здесь помогает показать ошибку раньше.
        elif order_type and order_type.name == OrderType.TYPE_REPAIR and \
             status != Order.STATUS_NEW and not performer:
            # Эта ветка elif означает, что status НЕ Order.STATUS_ISSUED
            self.add_error('performer',
                           ValidationError(f"Поле 'Исполнитель' обязательно для типа заказа '{OrderType.TYPE_REPAIR}', "
                                           f"если статус не '{dict(Order.STATUS_CHOICES).get(Order.STATUS_NEW)}'.",
                                           code='performer_required_for_repair_if_not_new_form'))

        return cleaned_data