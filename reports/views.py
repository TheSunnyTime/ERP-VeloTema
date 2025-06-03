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
from datetime import date, timedelta
import datetime
from django import forms

from products.models import Product
from salary_management.models import SalaryCalculation, SalaryPayment
from cash_register.models import CashTransaction, ExpenseCategory
from .models import ExpenseReportProxy, StockSummaryReportProxy # Добавил StockSummaryReportProxy для 'opts'

from django.contrib import admin


# --- ФУНКЦИЯ stock_summary_report С ОТЛАДКОЙ ---
@staff_member_required
def stock_summary_report(request):
    # --- ОТЛАДКА ---
    print(f"--- Отчет: Сводка по остаткам (stock_summary_report) ---")
    print(f"Пользователь: {request.user.username}")
    print(f"request.user.is_active: {request.user.is_active}")
    print(f"request.user.is_staff: {request.user.is_staff}")
    print(f"request.user.is_superuser: {request.user.is_superuser}")
    print(f"Имеет право 'reports.view_stock_summary_report': {request.user.has_perm('reports.view_stock_summary_report')}")
    # --- КОНЕЦ ОТЛАДКИ ---

    if not request.user.is_superuser and not request.user.has_perm('reports.view_stock_summary_report'):
        # --- ОТЛАДКА ---
        print("!!! stock_summary_report: ПРОВЕРКА ПРАВ НЕ ПРОЙДЕНА! Доступ запрещен.")
        # --- КОНЕЦ ОТЛАДКИ ---
        raise PermissionDenied("У тебя нет прав для просмотра этого отчета.")
    
    # --- ОТЛАДКА ---
    print("stock_summary_report: Проверка прав пройдена. Формируем отчет...")
    # --- КОНЕЦ ОТЛАДКИ ---
    
    products_in_stock = Product.objects.filter(stock_quantity__gt=0)
    
    total_cost_value = products_in_stock.aggregate(
        total=Sum(
            ExpressionWrapper(F('cost_price') * F('stock_quantity'),
                              output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    )['total'] or Decimal('0.00')
    
    total_retail_value = products_in_stock.aggregate(
        total=Sum(
            ExpressionWrapper(F('retail_price') * F('stock_quantity'),
                              output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    )['total'] or Decimal('0.00')
    
    expected_profit = products_in_stock.annotate(
        profit_per_item=ExpressionWrapper(F('retail_price') - F('cost_price'),
                                          output_field=DecimalField(max_digits=10, decimal_places=2))
    ).aggregate(
        total_profit=Sum(
            ExpressionWrapper(F('profit_per_item') * F('stock_quantity'),
                              output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    )['total_profit'] or Decimal('0.00')
    
    profit_calculation_hint = "(Розничная цена - Себестоимость) * Остаток на складе"

    context = {
        **admin.site.each_context(request),
        'title': 'Отчет: Сводка по остаткам товаров',
        'products_in_stock': products_in_stock,
        'total_cost_value': total_cost_value,
        'total_retail_value': total_retail_value,
        'expected_profit': expected_profit,
        'profit_calculation_hint': profit_calculation_hint,
        'app_label': 'reports',
        'opts': StockSummaryReportProxy._meta, # Передаем opts для хлебных крошек, если шаблон это использует
    }
    return render(request, 'admin/reports/stock_summary_report.html', context)


# --- Форма для фильтрации отчета по расходам ---
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

@staff_member_required(login_url='admin:login')
@permission_required('reports.view_expense_report', raise_exception=True)
def expense_report_view(request):
    report_data_grouped = {}
    
    if request.GET:
        form = ExpenseReportDateFilterForm(request.GET)
    else:
        initial_params = {'year': datetime.date.today().year, 'month': datetime.date.today().month}
        form = ExpenseReportDateFilterForm(data=initial_params) # Используем data для авто-валидации
        # Важно! Чтобы форма считалась "bound" и is_valid() отработал корректно с начальными данными,
        # передаем их через 'data', а не 'initial'.
        # Если form.is_valid() не вызывается далее явно перед использованием cleaned_data, 
        # то нужно вызвать form.is_valid() здесь, если мы хотим, чтобы cleaned_data было заполнено.
        # Однако, следующая логика уже предполагает, что form.is_valid() будет вызван.

    year_to_filter = None
    month_to_filter = None
    selected_period_display = ""

    if form.is_valid():
        year_to_filter = int(form.cleaned_data['year'])
        month_to_filter = int(form.cleaned_data['month'])
        selected_period_display = f"{dict(ExpenseReportDateFilterForm.MONTH_CHOICES)[month_to_filter]} {year_to_filter}"
    # Удален блок elif not request.GET, т.к. мы теперь всегда инициализируем форму с данными (GET или initial)
    # и полагаемся на form.is_valid()

    if year_to_filter and month_to_filter: # Только если год и месяц определены (форма валидна)
        transactions = CashTransaction.objects.filter(
            transaction_type=CashTransaction.TRANSACTION_TYPE_EXPENSE,
            timestamp__year=year_to_filter,
            timestamp__month=month_to_filter
        ).select_related('expense_category')

        expenses_by_category = transactions.values(
            'expense_category__name'
        ).annotate(
            total_spent=Sum('amount')
        ).order_by('expense_category__name')
        
        month_expenses = []
        for item in expenses_by_category:
            category_name = item['expense_category__name'] if item['expense_category__name'] else "Без категории"
            month_expenses.append({
                'category': category_name,
                'total': item['total_spent'] or Decimal('0.00')
            })
        
        if month_expenses:
            report_data_grouped[selected_period_display] = month_expenses
            
    context = {
        **admin.site.each_context(request),
        'title': f'Отчет по расходам {("за " + selected_period_display) if selected_period_display and form.is_valid() else ""}',
        'form': form,
        'report_data_grouped': report_data_grouped,
        'selected_period_display': selected_period_display if form.is_valid() else "", # Передаем, только если период валиден
        'opts': ExpenseReportProxy._meta,
        'app_label': ExpenseReportProxy._meta.app_label,
    }
    return render(request, 'admin/reports/expense_report.html', context)

# --- VIEW-ФУНКЦИЯ all_employees_salary_report_view (оставляем твой код) ---
@staff_member_required
def all_employees_salary_report_view(request):
    # ... (твой существующий код для этого отчета, как ты прислал) ...
    # (код этой функции остается без изменений, так как ты прислал его как рабочий)
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