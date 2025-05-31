# F:\CRM 2.0\ERP\orders\forms.py
from django import forms
from django.core.exceptions import ValidationError
from .models import Order # Импортируем Order для доступа к константам статуса
# Если в BaseOrderProductItemFormSet используется модель Product, ее нужно импортировать:
# from products.models import Product 

class BaseOrderProductItemFormSet(forms.BaseInlineFormSet):
    # Здесь твой существующий код для BaseOrderProductItemFormSet.
    # Оставляю его без изменений, так как он не был предметом текущей проблемы.
    def clean(self):
        super().clean()
        if not self.instance or not self.instance.pk: # self.instance это родительский Order
            return

        # Закомментированная логика проверки остатков (ты сказал, что пока полагаешься на OrderAdmin.save_related)
        # product_quantities = {}
        # for form in self.forms:
        #     if not form.is_valid():
        #         continue
        #     if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
        #         product = form.cleaned_data.get('product')
        #         quantity = form.cleaned_data.get('quantity')
        #         if product and quantity is not None and quantity > 0:
        #             product_quantities[product] = product_quantities.get(product, 0) + quantity
        # if not product_quantities:
        #     return
        # print(f"[FormSet CLEAN Order {self.instance.pk}] Проверяем остатки (в формсете) для статуса '{self.instance.status}': {product_quantities}")
        # all_forms_errors = []
        # # ... (логика проверки и добавления ошибок в all_forms_errors) ...
        # if all_forms_errors:
        #     raise ValidationError(all_forms_errors)
        pass # Если логики нет, можно просто pass


# --- ФОРМА ДЛЯ OrderAdmin ---
class OrderAdminForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = '__all__' # Админка сама будет управлять отображением полей через fieldsets

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        payment_method = cleaned_data.get('payment_method_on_closure')

        # self.instance.pk будет None для нового объекта (при создании)
        # self.instance будет объектом Order при редактировании
        is_new_object = not self.instance.pk 

        # 1. Проверка: Новый заказ не может быть сразу "Выдан"
        # Эту проверку также выполняет get_form в OrderAdmin, убирая опцию "Выдан",
        # но эта валидация - дополнительная защита на случай, если данные придут иначе.
        if is_new_object and status == Order.STATUS_ISSUED:
            # Вызываем ValidationError, которая будет показана как не-полевая ошибка (вверху формы)
            raise ValidationError(
                "Новый заказ не может быть сразу создан со статусом 'Выдан'. "
                "Сначала сохраните заказ (например, со статусом 'Новый'), добавьте позиции, "
                "затем укажите метод оплаты и измените статус на 'Выдан'."
            )

        # 2. Основная проверка: если статус "Выдан", метод оплаты должен быть указан
        # Эта проверка актуальна и для новых (если предыдущий if не сработал) и для существующих.
        if status == Order.STATUS_ISSUED and not payment_method:
            # Добавляем ошибку к конкретному полю payment_method_on_closure
            self.add_error('payment_method_on_closure', 
                           ValidationError("Метод оплаты должен быть указан, если статус заказа 'Выдан'.", 
                                           code='payment_method_required_for_issue'))
            # После add_error форма уже считается невалидной. 
            # Дополнительно вызывать raise ValidationError для всей формы не нужно,
            # если мы хотим, чтобы ошибка была привязана к полю.

        # Здесь можно добавить другие комплексные валидации для формы заказа, если они понадобятся
        
        return cleaned_data