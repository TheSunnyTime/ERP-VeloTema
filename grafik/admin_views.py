# grafik/admin_views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.template.loader import render_to_string
from django.contrib import admin
# from django.urls import reverse # Если не используется для отладки URL, можно убрать

@staff_member_required
def calendar_view(request):
    has_permission_to_view = request.user.has_perm('grafik.view_shift')
    context = {
        **admin.site.each_context(request),
        'title': 'Календарь смен', # Можно вернуть исходный заголовок или оставить тестовый
        'app_label': 'grafik',
        'has_permission': has_permission_to_view,
    }

    # --- ДИАГНОСТИЧЕСКИЙ ВЫВОД ---
    try:
        rendered_html_output = render_to_string('admin/grafik/calendar_view.html', context, request=request)
        print("\n" + "="*60)
        print("НАЧАЛО ОТЛАДКИ РЕНДЕРИНГА БЛОКА EXTRAJS (admin_views.py)")
        print("="*60)
        
        # Обновленный маркер, который должен присутствовать в вашем extrajs
        target_js_marker = "FullCalendar initialization script started" 
        
        if target_js_marker in rendered_html_output:
            print(f"+++ УСПЕХ (диагностика): Маркер '{target_js_marker}' НАЙДЕН в отрендеренном HTML.")
        else:
            # Если маркер все еще не найден, это может указывать на другие проблемы или на то,
            # что скрипт FullCalendar не попадает в extrajs по какой-то причине,
            # которую мы еще не выявили.
            print(f"--- ОШИБКА (диагностика): Маркер '{target_js_marker}' НЕ НАЙДЕН в отрендеренном HTML.")
            print("\n--- Сниппет конца отрендеренного HTML (последние 1500 символов): ---")
            print(rendered_html_output[-1500:]) # Полезно для анализа, что именно рендерится
            print("--- Конец сниппета ---")
        
        # Дополнительная проверка: ищем сам тег script FullCalendar
        fullcalendar_script_tag = "<script src=\"/static/grafik/vendor/fullcalendar/index.global.min.js\"></script>"
        if fullcalendar_script_tag in rendered_html_output:
            print(f"+++ УСПЕХ (диагностика): Тег подключения FullCalendar '{fullcalendar_script_tag}' НАЙДЕН.")
        else:
            print(f"--- ОШИБКА (диагностика): Тег подключения FullCalendar '{fullcalendar_script_tag}' НЕ НАЙДЕН.")

        print("="*60)
        print("КОНЕЦ ОТЛАДКИ РЕНДЕРИНГА БЛОКА EXTRAJS")
        print("="*60 + "\n")

    except Exception as e:
        print(f"ОШИБКА при попытке отрендерить шаблон в строку для диагностики: {e}")
    # --- КОНЕЦ ДИАГНОСТИЧЕСКОГО ВЫВОДА ---

    return render(request, 'admin/grafik/calendar_view.html', context)