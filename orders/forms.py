from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from dal import autocomplete
from django.db.models import Case, When
import logging  # <--- ВОТ ОН, НЕДОСТАЮЩИЙ ИМПОРТ
import json

# Импортируем только то, что действительно нужно
from .models import Order, OrderType, OrderProductItem, Service

# Получаем наш специальный логгер для поиска услуг
logger = logging.getLogger('service_search')

# --- ФОРМА для выбора товара в заказе ---
class OrderProductItemForm(forms.ModelForm):
    class Meta:
        model = OrderProductItem
        fields = '__all__'
        widgets = {
            'product': autocomplete.ModelSelect2(
                url='products:product-autocomplete',
                # --- ВОТ ОНА, ЭТА СТРОКА! ---
                # Этот атрибут говорит виджету, что он должен отображать HTML
                attrs={'data-html': True},
            ),
        }

# --- ФОРМАСЕТ для инлайнов товаров (оставь, если используешь) ---
class BaseOrderProductItemFormSet(forms.BaseInlineFormSet):
    pass

# --- ФОРМА ДЛЯ ЗАКАЗА (OrderAdminForm) ---
# Эту часть мы не трогаем, она отвечает за другую логику
class OrderAdminForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'performer' in self.fields:
            self.fields['performer'].required = False

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        order_type = cleaned_data.get('order_type')
        performer = cleaned_data.get('performer')
        payment_method_on_closure = cleaned_data.get('payment_method_on_closure')

        is_new_object = not self.instance or not self.instance.pk

        # Новый заказ не может быть сразу "Выдан"
        if is_new_object and status == Order.STATUS_ISSUED:
            self.add_error('status', ValidationError(
                "Новый заказ не может быть сразу создан со статусом 'Выдан'. "
                "Пожалуйста, выберите другой начальный статус."
            ))

        # Проверки для "Выдан"
        if status == Order.STATUS_ISSUED:
            if not payment_method_on_closure:
                self.add_error('payment_method_on_closure',
                                ValidationError("Метод оплаты должен быть указан, если статус заказа 'Выдан'.",
                                                code='payment_method_required_for_issue'))
            if order_type and order_type.name == OrderType.TYPE_REPAIR and not performer:
                self.add_error('performer',
                                ValidationError(f"Исполнитель должен быть указан для типа заказа '{OrderType.TYPE_REPAIR}' "
                                                f"при установке статуса 'Выдан'.",
                                                code='performer_required_for_repair_issue'))
        # Проверки для "Ремонт", если не "Новый" и не "Выдан"
        elif order_type and order_type.name == OrderType.TYPE_REPAIR and \
             status != Order.STATUS_NEW and not performer:
            self.add_error('performer',
                            ValidationError(f"Поле 'Исполнитель' обязательно для типа заказа '{OrderType.TYPE_REPAIR}', "
                                            f"если статус не '{dict(Order.STATUS_CHOICES).get(Order.STATUS_NEW)}'.",
                                            code='performer_required_for_repair_if_not_new_form'))
        return cleaned_data
    
class ServiceAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        """
        Финальная версия поиска, работающая в Python и включающая полное логирование.
        """
        if not self.q:
            return Service.objects.none()

        search_term = self.q.lower()
        
        logger.info(json.dumps({
            "event": "service_search_started",
            "query": self.q,
            "user": self.request.user.username,
        }, ensure_ascii=False))
        
        # 1. Получаем ВСЕ услуги из базы данных
        all_services = Service.objects.all()

        # 2. Фильтруем и ранжируем их в Python
        scored_services = []
        for service in all_services:
            service_name_lower = service.name.lower()
            score = 0
            score_details = {}
            
            # Логика начисления очков
            if search_term in service_name_lower:
                score += 10000
                score_details['substring_match'] = 10000
            
            if service_name_lower.startswith(search_term):
                score += 5000
                score_details['prefix_match'] = 5000
            
            if score > 0:
                scored_services.append({'service': service, 'score': score})
                # Логируем только те услуги, которые получили балл
                logger.debug(json.dumps({
                    "event": "service_scored", "query": self.q, "service_id": service.pk,
                    "service_name": service.name, "score": score, "score_details": score_details
                }, ensure_ascii=False))
        
        # 3. Сортируем найденные услуги по очкам
        scored_services.sort(key=lambda x: x['score'], reverse=True)

        # 4. Формируем итоговый queryset, сохраняя правильный порядок
        sorted_pks = [item['service'].pk for item in scored_services]

        if not sorted_pks:
            logger.info(json.dumps({
                "event": "service_search_completed_empty", "query": self.q, "results_count": 0
            }, ensure_ascii=False))
            return Service.objects.none()

        preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(sorted_pks)])
        final_queryset = Service.objects.filter(pk__in=sorted_pks).order_by(preserved_order)

        logger.info(json.dumps({
            "event": "service_search_completed", "query": self.q, "results_count": len(sorted_pks),
            "top_result_id": sorted_pks[0]
        }, ensure_ascii=False))
        
        return final_queryset

    def get_result_label(self, result):
        return f"{result.name} - {result.price} руб."

    def get_result_value(self, result):
        return str(result.pk)

    def get_selected_result_properties(self, result):
        return {'name': result.name, 'price': str(result.price)}