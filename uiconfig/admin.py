from django.contrib import admin
from .models import OrderStatusColor
from django.utils.html import format_html # Для отображения цвета

@admin.register(OrderStatusColor)
class OrderStatusColorAdmin(admin.ModelAdmin):
    list_display = ('get_status_display_name_admin', 'hex_color', 'display_color_preview_admin')
    list_editable = ('hex_color',) # Позволим редактировать цвет прямо из списка
    # search_fields = ('status_key',) # Поиск не так актуален при малом количестве статусов
    # list_filter = ('status_key',) # Фильтр тоже

    # Поля, которые будут отображаться в форме редактирования/добавления.
    # status_key будет выпадающим списком благодаря 'choices' в модели.
    fields = ('status_key', 'hex_color')

    def get_status_display_name_admin(self, obj):
        return obj.get_status_key_display() # Используем метод модели для отображения имени статуса
    get_status_display_name_admin.short_description = "Статус заказа" # Название колонки в админке

    def display_color_preview_admin(self, obj):
        if obj.hex_color:
            return format_html(
                '<div style="width: 50px; height: 20px; background-color: {}; border: 1px solid #ccc;"></div>',
                obj.hex_color
            )
        return "Нет цвета"
    display_color_preview_admin.short_description = "Предпросмотр цвета"

    # Ограничиваем доступ к этому разделу админки только для тех, кто имеет новое право
    # или является суперпользователем.
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.has_perm('uiconfig.can_manage_status_colors')

    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.has_perm('uiconfig.can_manage_status_colors')

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.has_perm('uiconfig.can_manage_status_colors')

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.has_perm('uiconfig.can_manage_status_colors')

    def has_module_permission(self, request):
        # Показываем модуль в списке приложений админки только если есть право или это суперюзер
        if request.user.is_superuser:
            return True
        return request.user.has_perm('uiconfig.can_manage_status_colors')