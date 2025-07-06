# orders/urls.py
from django.urls import path
from . import views # Импортируем views из текущего приложения orders
from . import api_views # Предполагаем, что создадим api_views.py
from .forms import ServiceAutocomplete # <-- ДОБАВЬ ЭТОТ ИМПОРТ

app_name = 'orders' # Имя пространства имен для URL-адресов этого приложения

urlpatterns = [
    # Твой существующий URL для получения цены услуги
    path('get-service-price/<int:service_id>/', views.get_service_price, name='get_service_price'),
    path('service-autocomplete/', ServiceAutocomplete.as_view(), name='service-autocomplete'),
    
    # Новый URL для API определения типа заказа
    path('api/determine-order-type/', views.determine_order_type_api_view, name='api_determine_order_type'),
    path('calculate-fifo-cost/', api_views.calculate_fifo_cost_api_view, name='calculate_fifo_cost_api'),
]