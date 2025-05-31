# ERP/urls.py (или F:\CRM 2.0\ERP\ERP\urls.py)
from django.contrib import admin
from django.urls import path, include

admin.site.site_header = "ERP 'ВелоТема'"
admin.site.site_title = "Портал ERP 'ВелоТема'"
admin.site.index_title = "Добро пожаловать в ERP 'ВелоТема'"
admin.site.site_url = None # Скрывает ссылку "Посмотреть сайт"

urlpatterns = [
    # Эти пути остаются для доступа к админкам других приложений через /admin/
    # Пространства имен здесь (reports, cash_register, utils) используются для удобства реверсирования
    # URL-адресов внутри этих админ-разделов, если они определены в соответствующих urls.py приложений.
    # Если в их urls.py есть app_name, то namespace здесь может быть избыточен, но не должен мешать, если уникален.
    path('admin/reports/', include('reports.urls', namespace='reports')), 
    path('admin/cash-register-reports/', include('cash_register.urls', namespace='cash_register')),
    path('admin/service-tools/', include('utils.urls', namespace='utils')), 
    
    # Основной путь админки Django
    path('admin/', admin.site.urls),

    # API для продуктов (оставляем как есть, если работает)
    # Убедись, что в products.urls есть app_name = 'products'
    path('products-api/', include('products.urls', namespace='products_api')), # Изменил namespace для уникальности, если в products.urls app_name='products'
                                                                             # Или если в products.urls нет app_name, то namespace='products' тут ок.
                                                                             # Либо просто: path('products-api/', include('products.urls')), если app_name в products.urls

    # --- ИЗМЕНЕНИЕ ЗДЕСЬ для orders ---
    # Подключаем orders.urls с префиксом 'orders-api/'.
    # Пространство имен 'orders' будет взято из app_name = 'orders' в файле orders.urls.py
    path('orders-api/', include('orders.urls')), 
    # Раньше было: path('orders-api/', include('orders.urls', namespace='orders')), 
    # убрали namespace='orders' отсюда, чтобы избежать конфликта с app_name='orders'
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---
]