# grafik/api_views.py
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
# from django.utils.dateparse import parse_datetime # Не используется, можно убрать
from datetime import datetime, timedelta

from .models import Shift

@staff_member_required # Доступ только для персонала
def shift_events_api(request):
    start_param = request.GET.get('start')
    end_param = request.GET.get('end')

    shifts_qs = Shift.objects.select_related('employee').all()

    if start_param and end_param:
        try:
            # FullCalendar передает даты в ISO 8601 формате.
            # Для dayGridMonth это могут быть просто даты 'YYYY-MM-DD'.
            # datetime.fromisoformat() может обрабатывать и 'YYYY-MM-DD' и 'YYYY-MM-DDTHH:MM:SSZ'
            # Убираем 'Z' и добавляем '+00:00' для совместимости, если время передается с Z.
            # Если время не передается, fromisoformat сам разберется.
            
            # Более надежный парсинг, если могут приходить только даты
            if 'T' not in start_param:
                 start_date = datetime.fromisoformat(start_param).date()
            else:
                 start_date = datetime.fromisoformat(start_param.replace('Z', '+00:00')).date()
            
            if 'T' not in end_param:
                end_date = datetime.fromisoformat(end_param).date()
            else:
                end_date = datetime.fromisoformat(end_param.replace('Z', '+00:00')).date()
            
            shifts_qs = shifts_qs.filter(date__gte=start_date, date__lt=end_date)
        except ValueError as e:
            # Лучше логировать ошибку, если параметры даты некорректны
            print(f"Error parsing date parameters: {e}. Start: {start_param}, End: {end_param}")
            # В случае ошибки можно вернуть пустой список или ошибку 400
            # return JsonResponse({'error': 'Invalid date format'}, status=400)
            pass # Пока оставляем как есть - вернет все смены, если парсинг не удался

    events = []
    for shift in shifts_qs:
        employee_name = shift.employee.get_full_name() or shift.employee.username
        
        start_datetime = datetime.combine(shift.date, shift.start_time)
        end_datetime = datetime.combine(shift.date, shift.end_time)

        if end_datetime < start_datetime: # Обработка смен, переходящих через полночь
            end_datetime += timedelta(days=1)

        shift_time_str = f"{shift.start_time.strftime('%H:%M')} - {shift.end_time.strftime('%H:%M')}"

        events.append({
            'id': shift.id,
            'title': employee_name, # Оставляем только имя сотрудника для стандартного title
            'start': start_datetime.isoformat(),
            'end': end_datetime.isoformat(),
            # 'notes': shift.notes, # Пока не используем, можно вернуть если нужно
            'employee_id': shift.employee.id,
            'extendedProps': { # <<< --- ДОБАВЛЯЕМ EXTENDEDPROPS ---
                'employee_name': employee_name, # Дублируем имя для явного доступа
                'shift_time_str': shift_time_str
            }
        })

    return JsonResponse(events, safe=False)