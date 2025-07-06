# orders/admin/service_admin_forms.py

from django import forms
from ..models import OrderServiceItem, Service
from decimal import Decimal

class OrderServiceItemAdminForm(forms.ModelForm):
    class Meta:
        model = OrderServiceItem
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.pk and instance.service and instance.price_at_order is not None:
            try:
                standard_price = instance.service.price
                if instance.price_at_order != standard_price:
                    self.fields['price_at_order'].widget.attrs['data-manual-price'] = 'true'
            except Service.DoesNotExist: 
                pass
            except Exception as e: 
                print(f"Error in OrderServiceItemAdminForm __init__ for service {instance.service_id}: {e}")