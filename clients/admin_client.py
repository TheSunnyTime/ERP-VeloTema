from django.contrib import admin
from django.utils.html import format_html
from .models import Client, ClientGroup
from orders.models import Order

class ClientGroupAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

class OrderInline(admin.TabularInline):
    model = Order
    fields = ['id', 'order_type', 'status', 'created_at']
    readonly_fields = ['id', 'order_type', 'status', 'created_at']
    extra = 0
    show_change_link = True
    ordering = ['-created_at']

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

admin.site.register(ClientGroup, ClientGroupAdmin)
admin.site.register(Client, ClientAdmin)