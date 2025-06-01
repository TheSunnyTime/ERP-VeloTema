# orders/admin/__init__.py
from django.contrib.auth.models import User # Для кастомизации __str__ User

# Импортируем админ-классы из других файлов этого пакета
from .order_type_admin import OrderTypeAdmin
from .service_admin import ServiceAdmin
from .order_admin import OrderAdmin
# Инлайны (OrderProductItemInline, OrderServiceItemInline) не нужно импортировать сюда,
# так как они не регистрируются напрямую, а используются в OrderAdmin.

# --- Модификация отображения User (можно оставить здесь или вынести) ---
if not hasattr(User, '__str_original_for_crm__'): 
    User.__str_original_for_crm__ = User.__str__ 
    def user_custom_display_name(self):
        if self.first_name:
            return self.first_name
        return self.username
    User.add_to_class("__str__", user_custom_display_name)
# --- Конец ---

# Вспомогательная функция (можно оставить здесь, если она не очень большая и используется в инлайнах/OrderAdmin)
# Или вынести в отдельный orders/admin/utils_admin.py и импортировать оттуда в order_inlines_admin.py и order_admin.py
def get_parent_order_from_request(request, obj_inline=None):
    if obj_inline and obj_inline.pk and hasattr(obj_inline, 'order'):
        return obj_inline.order
    # Нужен импорт Order для этой части:
    from ..models import Order 
    resolver_match = request.resolver_match
    if resolver_match and 'object_id' in resolver_match.kwargs:
        parent_order_id = resolver_match.kwargs['object_id']
        if parent_order_id:
            try:
                return Order.objects.get(pk=parent_order_id)
            except Order.DoesNotExist:
                return None
    return None

# Экспортируем для удобства, если где-то понадобится импорт из orders.admin
__all__ = [
    'OrderTypeAdmin',
    'ServiceAdmin',
    'OrderAdmin',
    'get_parent_order_from_request' 
    # Не включаем инлайны, так как они не для прямого импорта и регистрации
]