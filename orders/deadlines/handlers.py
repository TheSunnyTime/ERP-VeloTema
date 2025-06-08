# orders/deadlines/handlers.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from ..models import Order
# from .services import determine_and_update_order_due_date # Импорт новой функции, если будем использовать

@receiver(post_save, sender=Order)
def set_initial_order_due_date_handler(sender, instance, created, **kwargs):
    """
    Обработчик сигнала после сохранения заказа.
    Логика установки due_date теперь в основном в OrderAdmin.save_related.
    Этот сигнал может быть доработан или удален.
    """
    # if created and instance.due_date is None:
    #    # Здесь нужно будет передать корректные параметры в determine_and_update_order_due_date
    #    # was_complex_before_save будет False для created=True
    #    # original_order_type_name_before_determination можно считать None или текущим типом, если он уже есть
    #    is_complex_now = is_order_complex(instance) # Понадобится импорт is_order_complex
    #    new_due_date = determine_and_update_order_due_date(
    #        instance, 
    #        is_new_order=True, 
    #        was_complex_before_save=False,
    #        # is_complex_now - нужно определить на основе instance.service_items,
    #        # но они могут быть еще не сохранены, если сигнал срабатывает до сохранения инлайнов.
    #        # Это проблема для сигналов post_save, если логика зависит от связанных M2M или инлайнов.
    #        original_order_type_name_before_determination=None 
    #    )
    #    if new_due_date and new_due_date != instance.due_date:
    #        instance.due_date = new_due_date
    #        instance.save(update_fields=['due_date'])
    print(f"[Deadlines HANDLER set_initial_order_due_date_handler] Сигнал для заказа ID {instance.id}, created: {created}. Логика due_date перенесена в OrderAdmin.")
    pass # Пока ничего не делаем здесь