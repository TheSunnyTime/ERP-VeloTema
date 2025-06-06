from django.contrib import admin
from .models import OrderStatusColor
from django.utils.html import format_html # Для отображения цвета
from uiconfig.models import SupplyStatusColor, OrderDueDateColorRule
from .models import TaskStatusColor

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
@admin.register(SupplyStatusColor)
class SupplyStatusColorAdmin(admin.ModelAdmin):
    list_display = ('status_name', 'status_key', 'colored_status_preview', 'hex_color')
    list_editable = ('hex_color',)
    search_fields = ('status_name', 'status_key')
    ordering = ('status_name',)

    # Если ты определял кастомные права для модели, можно их здесь учитывать
    # def has_view_permission(self, request, obj=None):
    #     return request.user.has_perm('uiconfig.view_supplystatuscolor') or request.user.is_superuser
    # def has_change_permission(self, request, obj=None):
    #     return request.user.has_perm('uiconfig.change_supplystatuscolor') or request.user.is_superuser
    # def has_add_permission(self, request):
    #     return request.user.has_perm('uiconfig.add_supplystatuscolor') or request.user.is_superuser
    # def has_delete_permission(self, request, obj=None):
    #     return request.user.has_perm('uiconfig.delete_supplystatuscolor') or request.user.is_superuser

@admin.register(TaskStatusColor)
class TaskStatusColorAdmin(admin.ModelAdmin):
    list_display = ('get_status_name_for_admin_display', 'hex_color', 'display_color_preview_admin')
    list_editable = ('hex_color',)
    search_fields = ('task_status__name',) 
    autocomplete_fields = ['task_status'] 
    fields = ('task_status', 'hex_color') 

    def display_color_preview_admin(self, obj):
        if obj.hex_color:
            return format_html(
                '<div style="width: 50px; height: 20px; background-color: {}; border: 1px solid #ccc;"></div>',
                obj.hex_color
            )
        return "Нет цвета"
    display_color_preview_admin.short_description = "Предпросмотр цвета"
    # Не забудь, что метод get_status_name_for_admin_display должен быть в модели TaskStatusColor

@admin.register(OrderDueDateColorRule)
class OrderDueDateColorRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'priority', 'days_threshold', 'operator', 'hex_color', 'is_active')
    list_filter = ('is_active', 'operator')
    search_fields = ('name', 'hex_color')
    list_editable = ('priority', 'days_threshold', 'operator', 'hex_color', 'is_active')
    ordering = ('priority', 'id')

    fieldsets = (
        (None, {
            'fields': ('name', 'is_active', 'priority')
        }),
        ('Условие срабатывания (относительно сегодняшней даты)', {
            'fields': ('days_threshold', 'operator'),
            'description': ("<b>Пояснение:</b> 'Дней до срока' - это разница между датой выполнения заказа и сегодняшним днем. <br>"
                            "<b>Пример 1 (Просрочено):</b> Если 'дней до срока' <b><= -1</b>, цвет красный. (Порог: -1, Оператор: <=) <br>"
                            "<b>Пример 2 (Срок сегодня):</b> Если 'дней до срока' <b>== 0</b>, цвет оранжевый. (Порог: 0, Оператор: ==) <br>"
                            "<b>Пример 3 (Срок скоро):</b> Если 'дней до срока' <b><= 3</b> (и >=0), цвет желтый. (Порог: 3, Оператор: <=). Потребуется правило с более высоким приоритетом для 'срок сегодня'.")
        }),
        ('Оформление', {
            'fields': ('hex_color',)
        }),
    )