from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.contrib.auth.decorators import permission_required
from datetime import date
from calendar import monthrange
from .models import Shift

@staff_member_required
@permission_required('grafik.view_shift', raise_exception=True)
def calendar_view(request):
    has_permission_to_view = request.user.has_perm('grafik.view_shift')

    today = date.today()
    year = today.year
    month = today.month

    num_days = monthrange(year, month)[1]
    all_days = [date(year, month, day).strftime('%Y-%m-%d') for day in range(1, num_days + 1)]

    shifts = Shift.objects.filter(date__year=year, date__month=month)
    days_with_shifts = set()
    for s in shifts:
        days_with_shifts.add(s.date.strftime('%Y-%m-%d'))

    empty_days = [d for d in all_days if d not in days_with_shifts]

    context = {
        'title': 'Календарь смен',
        'app_label': 'grafik',
        'has_permission': has_permission_to_view,
        'empty_days': empty_days,
        'empty_hex': '#FFCCCC',
        'days_with_shifts': list(days_with_shifts),  # добавь для вывода отладки!
    }

    return render(request, 'admin/grafik/calendar_view.html', context)