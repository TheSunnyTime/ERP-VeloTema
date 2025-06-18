# F:\CRM 2.0\ERP\reports\views.py

from django.shortcuts import render
from django.core.exceptions import PermissionDenied
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.contrib.auth.models import User
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import permission_required
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta # Убедимся, что date и timedelta импортированы явно
import datetime # Оставим для ExpenseReportDateFilterForm, если он его использует неявно
from django import forms

from products.models import Product
from salary_management.models import SalaryCalculation, SalaryPayment
# --- ИЗМЕНЕНИЕ: Добавляем ExpenseCategory ---
from cash_register.models import CashTransaction, ExpenseCategory
from .models import ExpenseReportProxy, StockSummaryReportProxy

from .services import calculate_stock_report_data_fifo 

from django.contrib import admin


# --- stock_summary_report (БЕЗ ИЗМЕНЕНИЙ) ---
@staff_member_required
def stock_summary_report(request):
    if not request.user.is_superuser and not request.user.has_perm('reports.view_stock_summary_report'):
        raise PermissionDenied("У тебя нет прав для просмотра этого отчета.")
    report_data = calculate_stock_report_data_fifo()
    profit_calculation_hint = "(Общая розничная стоимость - Общая FIFO себестоимость)"
    context = {
        **admin.site.each_context(request),
        'title': 'Отчет: Сводка по остаткам товаров (FIFO)',
        'products_in_stock': report_data['products_data'],
        'total_cost_value': report_data['total_cost_fifo'],
        'total_retail_value': report_data['total_retail_value'],
        'expected_profit': report_data['expected_profit'],
        'profit_calculation_hint': profit_calculation_hint,
        'app_label': 'reports',
        'opts': StockSummaryReportProxy._meta,
    }
    return render(request, 'admin/reports/stock_summary_report.html', context)


# --- Форма для фильтрации отчета по расходам (БЕЗ ИЗМЕНЕНИЙ) ---
class ExpenseReportDateFilterForm(forms.Form):
    current_year = datetime.date.today().year
    current_month = datetime.date.today().month

    YEAR_CHOICES = [(year, str(year)) for year in range(current_year - 4, current_year + 2)]
    MONTH_CHOICES = [
        (1, 'Январь'), (2, 'Февраль'), (3, 'Март'), (4, 'Апрель'),
        (5, 'Май'), (6, 'Июнь'), (7, 'Июль'), (8, 'Август'),
        (9, 'Сентябрь'), (10, 'Октябрь'), (11, 'Ноябрь'), (12, 'Декабрь')
    ]

    year = forms.ChoiceField(choices=YEAR_CHOICES, initial=current_year, label="Год", required=True)
    month = forms.ChoiceField(choices=MONTH_CHOICES, initial=current_month, label="Месяц", required=True)

# --- ОБНОВЛЕННАЯ VIEW-ФУНКЦИЯ expense_report_view ---
@staff_member_required(login_url='admin:login')
@permission_required('reports.view_expense_report', raise_exception=True)
def expense_report_view(request):
    today = timezone.now().date()
    
    # --- НАЧАЛО ИЗМЕНЕНИЙ: Логика определения выбранного периода и редиректа ---
    selected_year = request.GET.get('year')
    selected_month = request.GET.get('month')

    if not selected_year or not selected_month:
        # Если параметры не заданы, используем текущий месяц и год
        # или можно сделать редирект на предыдущий, как в отчете по ЗП, если нужно
        default_year = today.year
        default_month = today.month
        # Редирект, чтобы URL всегда содержал параметры года и месяца
        query_params = f'?year={default_year}&month={default_month}'
        return HttpResponseRedirect(reverse('reports:expense_report') + query_params)

    try:
        year_to_filter = int(selected_year)
        month_to_filter = int(selected_month)
        if not (1 <= month_to_filter <= 12):
            raise ValueError("Month out of range")
    except (ValueError, TypeError):
        # Если параметры некорректны, редирект на текущий месяц
        default_year = today.year
        default_month = today.month
        query_params = f'?year={default_year}&month={default_month}'
        return HttpResponseRedirect(reverse('reports:expense_report') + query_params)

    form_initial = {'year': year_to_filter, 'month': month_to_filter}
    form = ExpenseReportDateFilterForm(request.GET or form_initial) # Используем GET или initial

    selected_period_display = ""
    if form.is_valid(): # Проверяем валидность, даже если данные из URL
        # year_to_filter и month_to_filter уже установлены из URL
        selected_period_display = f"{dict(ExpenseReportDateFilterForm.MONTH_CHOICES)[month_to_filter]} {year_to_filter}"
    # --- КОНЕЦ ИЗМЕНЕНИЙ: Логика определения выбранного периода ---

    mandatory_expenses_data = []
    optional_expenses_data = []
    total_mandatory_spent = Decimal('0.00')
    total_optional_spent = Decimal('0.00')

    if form.is_valid(): # Основная логика получения данных только если форма валидна
        transactions = CashTransaction.objects.filter(
            transaction_type=CashTransaction.TRANSACTION_TYPE_EXPENSE,
            timestamp__year=year_to_filter,
            timestamp__month=month_to_filter
        ).select_related('expense_category')

        # Обязательные расходы
        mandatory_q = transactions.filter(
            expense_category__expense_type_category=ExpenseCategory.CATEGORY_MANDATORY
        ).values(
            'expense_category__name'
        ).annotate(
            total_spent_for_category=Sum('amount')
        ).order_by('expense_category__name')

        for item in mandatory_q:
            category_name = item['expense_category__name'] if item['expense_category__name'] else "Без категории (Обяз.)"
            amount = item['total_spent_for_category'] or Decimal('0.00')
            mandatory_expenses_data.append({
                'category': category_name,
                'total': amount
            })
            total_mandatory_spent += amount

        # Необязательные расходы
        optional_q = transactions.filter(
            expense_category__expense_type_category=ExpenseCategory.CATEGORY_OPTIONAL
        ).values(
            'expense_category__name'
        ).annotate(
            total_spent_for_category=Sum('amount')
        ).order_by('expense_category__name')

        for item in optional_q:
            category_name = item['expense_category__name'] if item['expense_category__name'] else "Без категории (Необяз.)"
            amount = item['total_spent_for_category'] or Decimal('0.00')
            optional_expenses_data.append({
                'category': category_name,
                'total': amount
            })
            total_optional_spent += amount
            
    # --- НАЧАЛО ИЗМЕНЕНИЙ: Логика для навигации по месяцам ---
    current_period_start_nav = date(year_to_filter, month_to_filter, 1)
    
    prev_month_date_nav = current_period_start_nav - timedelta(days=1) # Последний день предыдущего месяца
    prev_month_url = reverse('reports:expense_report') + f'?year={prev_month_date_nav.year}&month={prev_month_date_nav.month}'

    next_month_first_day_nav = (current_period_start_nav + timedelta(days=32)).replace(day=1) # Первый день следующего месяца
    show_next_month_link = True
    if next_month_first_day_nav.year > today.year or \
       (next_month_first_day_nav.year == today.year and next_month_first_day_nav.month > today.month):
        show_next_month_link = False
    
    next_month_url = None
    if show_next_month_link:
        next_month_url = reverse('reports:expense_report') + f'?year={next_month_first_day_nav.year}&month={next_month_first_day_nav.month}'
    # --- КОНЕЦ ИЗМЕНЕНИЙ: Логика для навигации по месяцам ---

    context = {
        **admin.site.each_context(request),
        'title': f'Отчет по расходам {("за " + selected_period_display) if selected_period_display and form.is_valid() else ""}',
        'form': form,
        # --- ИЗМЕНЕНИЕ: Передаем новые данные в контекст ---
        'mandatory_expenses': mandatory_expenses_data,
        'optional_expenses': optional_expenses_data,
        'total_mandatory_spent': total_mandatory_spent,
        'total_optional_spent': total_optional_spent,
        'selected_period_display': selected_period_display if form.is_valid() else "", # Для заголовка и навигации
        'current_selected_year': year_to_filter, # Для отображения в навигации
        'current_selected_month': month_to_filter, # Для отображения в навигации
        'prev_month_url': prev_month_url,
        'next_month_url': next_month_url,
        'show_next_month_link': show_next_month_link,
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---
        'opts': ExpenseReportProxy._meta,
        'app_label': ExpenseReportProxy._meta.app_label,
    }
    return render(request, 'admin/reports/expense_report.html', context)

# --- all_employees_salary_report_view (БЕЗ ИЗМЕНЕНИЙ) ---
@staff_member_required
def all_employees_salary_report_view(request):
    # ... (ваш существующий код для этого отчета остается здесь без изменений) ...
    if not request.user.has_perm('reports.view_all_employee_salaries'):
        raise PermissionDenied("У тебя нет прав для просмотра этого отчета.")
    today = timezone.now().date()
    try: selected_year = int(request.GET.get('year', ''))
    except (ValueError, TypeError): selected_year = None
    try: selected_month = int(request.GET.get('month', ''))
    except (ValueError, TypeError): selected_month = None
    try: selected_employee_id = int(request.GET.get('employee_id', ''))
    except (ValueError, TypeError): selected_employee_id = None
    if not selected_year or not selected_month or not (1 <= selected_month <= 12):
        first_day_of_current_month = today.replace(day=1)
        last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
        default_redirect_year = last_day_of_previous_month.year
        default_redirect_month = last_day_of_previous_month.month
        selected_year = default_redirect_year
        selected_month = default_redirect_month
        if 'year' not in request.GET or 'month' not in request.GET:
            query_params = f'?year={selected_year}&month={selected_month}'
            if selected_employee_id is not None : query_params += f'&employee_id={selected_employee_id}'
            return HttpResponseRedirect(reverse('reports:all_employees_salary_report') + query_params)
    all_employees = User.objects.filter(is_active=True, is_staff=True).order_by('last_name', 'first_name', 'username')
    employees_to_report_qs = User.objects.filter(is_active=True, is_staff=True)
    if selected_employee_id: employees_to_report_qs = employees_to_report_qs.filter(pk=selected_employee_id)
    report_data = []
    grand_total_opening_balance = Decimal('0.00')
    grand_total_accrued_for_period = Decimal('0.00')
    grand_total_paid_for_period = Decimal('0.00')
    grand_total_closing_balance = Decimal('0.00')
    start_of_selected_period = date(selected_year, selected_month, 1)
    for emp in employees_to_report_qs:
        accrued_before = SalaryCalculation.objects.filter(employee=emp, period_date__lt=start_of_selected_period).aggregate(total=Sum('total_calculated_amount'))['total'] or Decimal('0.00')
        paid_before_years = SalaryPayment.objects.filter(employee=emp, payment_for_year__lt=selected_year).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        paid_before_months_current_year = SalaryPayment.objects.filter(employee=emp, payment_for_year=selected_year, payment_for_month__lt=selected_month).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        paid_before = paid_before_years + paid_before_months_current_year
        opening_balance = accrued_before - paid_before
        calculations_period = SalaryCalculation.objects.filter(employee=emp, period_date__year=selected_year, period_date__month=selected_month)
        accrued_period = calculations_period.aggregate(total=Sum('total_calculated_amount'))['total'] or Decimal('0.00')
        payments_period = SalaryPayment.objects.filter(employee=emp, payment_for_year=selected_year, payment_for_month=selected_month)
        paid_period = payments_period.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        closing_balance = opening_balance + accrued_period - paid_period
        report_data.append({
            'employee_id': emp.id,
            'employee_name': emp.first_name if emp.first_name else emp.username,
            'opening_balance': opening_balance,
            'accrued_period': accrued_period,
            'paid_period': paid_period,
            'closing_balance': closing_balance,
            'calculations_for_period': calculations_period.order_by('order__id', 'role_context'),
            'payments_for_period': payments_period.order_by('payment_date'),
        })
        grand_total_opening_balance += opening_balance
        grand_total_accrued_for_period += accrued_period
        grand_total_paid_for_period += paid_period
        grand_total_closing_balance += closing_balance
    current_period_start_nav = date(selected_year, selected_month, 1)
    prev_month_date = current_period_start_nav - timedelta(days=1)
    prev_month_url_params = f'?year={prev_month_date.year}&month={prev_month_date.month}'
    if selected_employee_id: prev_month_url_params += f'&employee_id={selected_employee_id}'
    prev_month_url = reverse('reports:all_employees_salary_report') + prev_month_url_params
    next_month_date = (current_period_start_nav + timedelta(days=32)).replace(day=1)
    show_next_month = True
    if next_month_date.year > today.year or (next_month_date.year == today.year and next_month_date.month > today.month): show_next_month = False
    next_month_url = None
    if show_next_month:
        next_month_url_params = f'?year={next_month_date.year}&month={next_month_date.month}'
        if selected_employee_id: next_month_url_params += f'&employee_id={selected_employee_id}'
        next_month_url = reverse('reports:all_employees_salary_report') + next_month_url_params
    context = {
        **admin.site.each_context(request),
        'title': f'Сводный отчет по зарплате за {selected_month:02}.{selected_year}',
        'report_data': report_data,
        'all_employees': all_employees,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'selected_employee_id': selected_employee_id,
        'grand_total_opening_balance': grand_total_opening_balance,
        'grand_total_accrued_for_period': grand_total_accrued_for_period,
        'grand_total_paid_for_period': grand_total_paid_for_period,
        'grand_total_closing_balance': grand_total_closing_balance,
        'prev_month_url': prev_month_url,
        'next_month_url': next_month_url,
        'is_current_month_selected': (selected_year == today.year and selected_month == today.month),
        'app_label': 'reports',
    }
    return render(request, 'admin/reports/all_employees_salary_report.html', context)