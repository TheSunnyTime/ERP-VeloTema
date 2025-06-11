# grafik/urls.py
from django.urls import path
from . import admin_views # Импортируем наши admin_views
from . import api_views # <--- НОВЫЙ ИМПОРТ

app_name = 'grafik' # Имя приложения для пространства имен URL

urlpatterns = [
    # URL для кастомного представления календаря в админке (оставляем как есть, если регистрируется через AdminSite)
    # path('calendar/', admin_views.calendar_view, name='calendar_view_custom'),

    # --- НОВЫЙ URL ДЛЯ API ---
    path('api/shift_events/', api_views.shift_events_api, name='shift_events_api'),
]