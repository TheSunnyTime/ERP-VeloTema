# orders/urls.py
from django.urls import path
from . import views # Импортируем views из текущего приложения orders

app_name = 'orders' # Имя пространства имен для URL-адресов этого приложения

urlpatterns = [
    # Твой существующий URL для получения цены услуги
    path('get-service-price/<int:service_id>/', views.get_service_price, name='get_service_price'),
    
    # Новый URL для API определения типа заказа
    path('api/determine-order-type/', views.determine_order_type_api_view, name='api_determine_order_type'),
    
    # Сюда в будущем можно будет добавлять другие URL-адреса для приложения orders
]