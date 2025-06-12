from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from datetime import datetime, timedelta

from .models import Shift

@staff_member_required
def shift_events_api(request):
    start_param = request.GET.get('start')
    end_param = request.GET.get('end')

    shifts_qs = Shift.objects.select_related('employee').all()

    # Фильтрация по дате (если параметры переданы)
    if start_param and end_param:
        try:
            # Преобразуем параметры в дату
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
            print(f"Ошибка разбора дат: {e}. Start: {start_param}, End: {end_param}")
            pass

    events = []
    for shift in shifts_qs:
        employee_name = shift.employee.get_full_name() or shift.employee.username

        start_datetime = datetime.combine(shift.date, shift.start_time)
        end_datetime = datetime.combine(shift.date, shift.end_time)
        if end_datetime < start_datetime:
            end_datetime += timedelta(days=1)

        shift_time_str = f"{shift.start_time.strftime('%H:%M')} - {shift.end_time.strftime('%H:%M')}"

        events.append({
            'id': shift.id,
            'title': employee_name,
            'start': start_datetime.isoformat(),
            'end': end_datetime.isoformat(),
            'employee_id': shift.employee.id,
            'extendedProps': {
                'employee_name': employee_name,
                'shift_time_str': shift_time_str,
            }
        })

    return JsonResponse(events, safe=False)