# orders/deadlines/services.py
from django.utils import timezone
from datetime import timedelta

def calculate_initial_due_date(order_instance):
    """
    Рассчитывает плановую дату выполнения для нового заказа.
    Логика: +3 календарных дня с момента создания заказа.
    """
    # Предполагаем, что у заказа есть поле created_at, которое устанавливается при создании.
    # В сигнале post_save (где created=True) это поле уже будет заполнено.
    if hasattr(order_instance, 'created_at') and order_instance.created_at:
        base_date = order_instance.created_at
    else:
        # Если поля created_at нет, или оно по какой-то причине не установлено,
        # используем текущее время как базу.
        # Это также будет работать, если created_at еще не записано в БД до первого save(),
        # но в post_save оно уже должно быть.
        base_date = timezone.now()
    
    return (base_date + timedelta(days=3)).date()