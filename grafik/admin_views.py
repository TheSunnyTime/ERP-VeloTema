# grafik/admin_views.py
from django.contrib import admin # Для доступа к admin.site.site_header и т.д.
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
# from django.urls import path # path здесь не нужен, он используется в urls.py

@staff_member_required # Доступ только для персонала (админов)
def calendar_view(request):
    # Проверяем, есть ли у пользователя право на просмотр смен.
    # Это базовое право, можно будет сделать более гранулированное кастомное право на просмотр календаря.
    has_permission_to_view = request.user.has_perm('grafik.view_shift') 

    context = {
        'title': 'Календарь смен',
        # Передаем базовые переменные для админ-шаблона, чтобы он выглядел как часть админки
        'site_header': admin.site.site_header,
        'site_title': admin.site.site_title,
        'app_label': 'grafik', # Чтобы хлебные крошки могли правильно построиться (опционально)
        'has_permission': has_permission_to_view, 
    }
    return render(request, 'admin/grafik/calendar_view.html', context)