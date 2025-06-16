from django.contrib import admin
from django.utils.html import format_html
from .models import Client, ClientGroup
from orders.models import Order

class OrderInline(admin.TabularInline):
    model = Order
    can_delete = False
    fields = ['id', 'order_type', 'colored_status', 'order_total', 'created_at']
    readonly_fields = ['id', 'order_type', 'colored_status', 'order_total', 'created_at']
    extra = 0
    show_change_link = True
    ordering = ['-created_at']

    def colored_status(self, obj):
        # Подсветка статуса (замени цвета под себя)
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
         # УБИРАЕМ 'admin/js/jquery.init.js', # Django сам загрузит jQuery и создаст django.jQuery
            'vendor/inputmask/jquery.inputmask.js', # Путь к библиотеке Inputmask
            'clients/js/client_form_masks.js',      # Путь к твоему кастомному JS
        )

class ClientGroupAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

admin.site.register(ClientGroup, ClientGroupAdmin)
admin.site.register(Client, ClientAdmin)

