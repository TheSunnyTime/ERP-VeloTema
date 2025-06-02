# F:\CRM 2.0\ERP\products\urls.py
from django.urls import path
from . import views # Импортируем views из текущего приложения products

app_name = 'products' # <--- ОЧЕНЬ ВАЖНО: имя приложения для пространства имен URL

urlpatterns = [
    # Этот URL мы создавали для динамического получения цены товара
    path('get-price/<int:product_id>/', views.get_product_price_api_view, name='get_product_price_api'),
    # Здесь НЕ должно быть строки path('products-api/', include('products.urls', ...))
    # Сюда можно добавлять другие URL, специфичные для приложения products, если они понадобятся
]