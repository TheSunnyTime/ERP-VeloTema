# products/pricetags/urls.py
from django.urls import path
from . import views

app_name = 'pricetags' # Пространство имен для этого подмодуля

urlpatterns = [
    path('select/', views.select_products_for_pricetags, name='select_products'),
    path('generate-pdf/', views.generate_pricetags_pdf, name='generate_pdf'), # НОВЫЙ URL
    path('get-product-data/<int:product_id>/', views.get_product_data_api_view, name='get_product_data_api'), # НОВЫЙ URL
]