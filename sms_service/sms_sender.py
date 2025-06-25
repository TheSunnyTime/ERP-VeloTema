# Файл для автоматической отправки SMS при создании заказов
from django.utils import timezone
from .models import SMSTemplate, SMSMessage
from .rocket_sms_api import RocketSMSAPI
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

def send_new_order_sms(order):
    """
    Отправляет SMS клиенту при создании нового заказа
    order - объект заказа
    """
    
    # Проверяем что у заказа есть ID
    if not order.pk:
        logger.warning(f"Заказ не имеет ID - SMS не отправляется")
        return False
    
    # Проверяем есть ли телефон у клиента
    if not order.client or not order.client.phone:
        logger.info(f"Заказ {order.pk}: у клиента нет телефона")
        return False
    
    # Проверяем не отправляли ли уже SMS для этого заказа
    existing_sms = SMSMessage.objects.filter(
        phone_number=order.client.phone,
        message_text__contains=f"№{order.pk}"
    ).exists()
    
    if existing_sms:
        logger.info(f"Заказ {order.pk}: SMS уже отправлялась")
        return False
    
 # Определяем тип шаблона по типу заказа
    if order.order_type and order.order_type.name == 'Ремонт':
        template_code = 'new_order_repair'
    elif order.order_type and order.order_type.name == 'Продажа':
        template_code = 'new_order_sale'
    elif order.order_type and order.order_type.name == 'Определить':
        # Для типа "Определить" используем шаблон ремонта по умолчанию
        template_code = 'new_order_repair'
        logger.info(f"Заказ {order.pk}: тип 'Определить', используем шаблон ремонта")
    else:
        logger.warning(f"Заказ {order.pk}: неизвестный тип заказа {order.order_type}")
        template_code = 'new_order_repair'  # По умолчанию берем ремонт
    
    # Ищем шаблон
    try:
        template = SMSTemplate.objects.get(
            template_code=template_code,
            is_active=True
        )
    except SMSTemplate.DoesNotExist:
        logger.error(f"Не найден активный шаблон {template_code}")
        return False
    
    # Подготавливаем переменные для замены
    variables = {
        'client_name': order.client.name,
        'order_number': str(order.pk),
        'order_type': str(order.order_type) if order.order_type else "Заказ",
        'total_amount': f"{order.calculate_total_amount():.2f}",
        'due_date': order.due_date.strftime('%d.%m.%Y') if order.due_date else "уточняется",
        'product_name': _get_order_products_text(order)
    }
    
    # Заменяем переменные в тексте
    message_text = template.message_text
    for key, value in variables.items():
        message_text = message_text.replace(f'{{{key}}}', str(value))
    
    # Находим админа для отправки SMS
    try:
        admin_user = User.objects.filter(is_staff=True).first()
        if not admin_user:
            logger.error("Не найден пользователь-администратор для отправки SMS")
            return False
    except Exception as e:
        logger.error(f"Ошибка поиска администратора: {e}")
        return False
    
    # Отправляем SMS через твой существующий API
    api = RocketSMSAPI()
    result = api.send_single_sms(
        phone_number=order.client.phone,
        message_text=message_text,
        user=admin_user,
        recipient_name=order.client.name
    )
    
    if result.get('success'):
        logger.info(f"Заказ {order.pk}: SMS отправлена успешно, ID: {result.get('message_id')}")
        return True
    else:
        logger.error(f"Заказ {order.pk}: ошибка отправки SMS - {result.get('error')}")
        return False

def _get_order_products_text(order):
    """
    Получает текст с товарами/услугами из заказа
    """
    items = []
    
    # Добавляем товары из заказа
    for item in order.product_items.all():
        if item.product:
            items.append(item.product.name)
    
    # Добавляем услуги из заказа
    for service_item in order.service_items.all():
        if service_item.service:
            items.append(service_item.service.name)
    
    # Если есть описание изделия в ремонт - добавляем его
    if order.repaired_item:
        items.insert(0, order.repaired_item)
    
    if items:
        return ", ".join(items[:3])  # Берем только первые 3 позиции
    else:
        return "Заказ принят"