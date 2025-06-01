# ERP/urls.py (или F:\CRM 2.0\ERP\ERP\urls.py)
from django.contrib import admin
from django.urls import path, include

admin.site.site_header = "ERP 'ВелоТема'"
admin.site.site_title = "Портал ERP 'ВелоТема'"
admin.site.index_title = "Добро пожаловать в ERP 'ВелоТема'"
admin.site.site_url = None # Скрывает ссылку "Посмотреть сайт"

urlpatterns = [
    # 1. Пути для кастомных view внутри админки (если они действительно предназначены только для админ-интерфейса)
    # Если 'reports.urls', 'cash_register.urls', 'utils.urls' (для service-tools) 
    # содержат URL-ы, которые являются ЧАСТЬЮ админки и используют admin.site.admin_view,
    # то их можно оставить с префиксом /admin/.
    # Однако, если это просто кастомные страницы, не являющиеся стандартными ModelAdmin,
    # то лучше вынести их из-под /admin/, чтобы не путать с настоящими админ-страницами.
    # Пока оставляю как у тебя, но с уникальными namespace, если в app-файлах есть app_name.
    
    path('admin/reports/', include('reports.urls', namespace='custom_reports_admin')), # Используем уникальный namespace
    path('admin/cash-register-reports/', include('cash_register.urls', namespace='custom_cash_register_admin')), # Используем уникальный namespace
    # path('admin/service-tools/', include('utils.urls', namespace='utils_admin')), # Пока закомментирую, так как мы utils вынесем

    # 2. Основной путь админки Django (должен идти после кастомных admin/ путей, если они есть, или до них, если они не пересекаются)
    path('admin/', admin.site.urls),

    # 3. API эндпоинты (не часть админки)
    # Предполагаем, что в products/urls.py есть app_name = 'products'
    path('products-api/', include('products.urls')), 
    
    # Подключаем orders.urls с префиксом 'orders-api/'.
    # Пространство имен 'orders' будет взято из app_name = 'orders' в файле orders.urls.py
    path('orders-api/', include('orders.urls')), 
    
    # --- НОВОЕ ПОДКЛЮЧЕНИЕ ДЛЯ UTILS ---
    # Подключаем utils.urls с префиксом 'utils/'.
    # Пространство имен 'utils' будет взято из app_name = 'utils' в файле utils.urls.py
    path('utils/', include('utils.urls')), # <--- ДОБАВЛЕНО ДЛЯ /utils/export-stock-levels/
                                          # Убедись, что в utils/urls.py есть app_name = 'utils'
]