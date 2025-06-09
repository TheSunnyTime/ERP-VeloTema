# ERP/urls.py
from django.contrib import admin
from django.urls import path, include

admin.site.site_header = "ERP 'ВелоТема'"
admin.site.site_title = "Портал ERP 'ВелоТема'"
admin.site.index_title = "Добро пожаловать в ERP 'ВелоТема'"
admin.site.site_url = None # Скрывает ссылку "Посмотреть сайт"

urlpatterns = [
    # 1. Кастомные URL-адреса, интегрированные в админку (если есть)
    # Эти пути обычно ведут на views, которые рендерят страницы внутри админ-интерфейса.
    # Использование уникальных namespace здесь - хорошая практика, если app_name в 
    # соответствующем urls.py может использоваться и для других целей.
    path('admin/reports/', include('reports.urls', namespace='custom_reports_admin')), 
    path('admin/cash-register-reports/', include('cash_register.urls', namespace='custom_cash_register_admin')),
    path('grafik/', include('grafik.urls', namespace='grafik')), # ДОБАВИТЬ ЭТУ СТРОКУ
    # path('admin/service-tools/', include('utils.urls', namespace='utils_admin_custom')), # Мы решили utils.urls подключать отдельно

    # 2. Основные URL-адреса админки Django
    # Должны идти после более специфичных путей, начинающихся с 'admin/', если такие есть.
    path('admin/', admin.site.urls),

    # 3. URL-адреса приложений (API и кастомные страницы вне стандартной админки)
    
    # API для продуктов
    # Предполагается, что в products/urls.py определен app_name = 'products'
    # или здесь можно было бы указать namespace, если app_name там нет.
    path('products-api/', include('products.urls')), 
    
    # API для заказов
    # Предполагается, что в orders/urls.py определен app_name = 'orders'
    path('orders-api/', include('orders.urls')), 
    
    # Утилиты (включая нашу страницу выгрузки остатков)
    # Предполагается, что в utils/urls.py определен app_name = 'utils'
    path('utils/', include('utils.urls')), 
    
    # Поставщики (включая нашу страницу импорта позиций поставки)
    # Предполагается, что в suppliers/urls.py определен app_name = 'suppliers'
    path('suppliers/', include('suppliers.urls')), 
]