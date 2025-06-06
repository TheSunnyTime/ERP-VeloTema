# orders/deadlines/handlers.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from ..models import Order # Используем относительный импорт для доступа к Order из orders/models.py
from .services import calculate_initial_due_date

@receiver(post_save, sender=Order)
def set_initial_order_due_date_handler(sender, instance, created, **kwargs):
    """
    Обработчик сигнала после сохранения заказа.
    Если заказ только что создан и у него еще нет срока выполнения,
    рассчитывает и сохраняет его.
    """
    if created and instance.due_date is None:
        instance.due_date = calculate_initial_due_date(instance)
        # Сохраняем только обновленное поле, чтобы избежать рекурсивного вызова сигнала
        # и не перезаписывать другие возможные изменения, сделанные в другом месте.
        instance.save(update_fields=['due_date'])