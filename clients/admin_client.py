from django.contrib import admin
from django.utils.html import format_html
from .models import Client, ClientGroup
from orders.models import Order

class OrderInline(admin.TabularInline):
    model = Order
    can_delete = False
    fields = ['order_link', 'order_type_readonly', 'colored_status', 'order_total', 'created_at']
    readonly_fields = ['order_link', 'order_type_readonly', 'colored_status', 'order_total', 'created_at']
    extra = 0
    show_change_link = True
    ordering = ['-created_at']

    def has_add_permission(self, request, obj):
        # Убираем кнопку "Добавить ещё один Заказ"
        return False

    def order_link(self, obj):
        url = f"/admin/orders/order/{obj.id}/change/"
        date_str = obj.created_at.strftime('%d.%m.%Y %H:%M')
        return format_html(
            '<a href="{}" target="_blank">Заказ №{} от {}</a>',
            url,
            obj.id,
            date_str
        )
    order_link.short_description = 'Заказ'

    def order_type_readonly(self, obj):
        return obj.order_type.name if obj.order_type else "-"
    order_type_readonly.short_description = 'Тип заказа'

    def colored_status(self, obj):
        color_map = {
            'new': 'orange',
            'in_progress': 'blue',
            'awaiting': 'gray',
            'ready': 'green',
            'no_answer': 'darkred',
            'delivering': 'purple',
            'issued': 'darkgreen',
            'cancelled': 'red',
        }
        color = color_map.get(obj.status, 'black')
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    colored_status.short_description = 'Статус'

    def order_total(self, obj):
        total = obj.calculate_total_amount()
        return f"{total} руб."
    order_total.short_description = 'Итоговая сумма'

class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'client_group', 'phone', 'email', 'contact_person', 'created_at')
    list_filter = ('client_group', 'created_at')
    search_fields = ('name', 'phone', 'email', 'contact_person', 'notes')
    autocomplete_fields = ('client_group',)
    readonly_fields = ('created_at',)
    inlines = [OrderInline]
    fieldsets = (
        (None, {
            'fields': (
                'name', 'phone', 'email', 'client_group', 'notes', 'created_at'
            )
        }),
    )
    class Media:
        js = (
            'vendor/inputmask/jquery.inputmask.js',
            'clients/js/client_form_masks.js',
        )

class ClientGroupAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

admin.site.register(ClientGroup, ClientGroupAdmin)
admin.site.register(Client, ClientAdmin)