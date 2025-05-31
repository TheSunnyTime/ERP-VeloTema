# F:\CRM 2.0\ERP\cash_register\views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required # Для проверки входа
from django.core.exceptions import PermissionDenied     # Для ошибки доступа
from django.contrib import admin                        # Для доступа к admin.site.site_header и т.д.
from .models import CashRegister, CashTransaction       # Наши модели кассы

# login_required здесь как базовая защита, основная проверка прав будет внутри
@login_required 
def cash_overview_report(request):
    # Проверяем кастомное право на просмотр этого отчета
    if not request.user.has_perm('reports.view_cash_overview_report'): # Обратите внимание: 'reports.' так как право определено в приложении reports
        raise PermissionDenied

    active_cash_registers = CashRegister.objects.filter(is_active=True)

    # Последние N приходных транзакций
    recent_income_transactions = CashTransaction.objects.filter(
        transaction_type=CashTransaction.TRANSACTION_TYPE_INCOME
    ).select_related('order', 'employee', 'cash_register').order_by('-timestamp')[:20] # Например, последние 20

    # Рассчитаем общие суммы по типам платежей для активных касс (пример)
    total_by_payment_method = {}
    # Это более сложный расчет, если кассы не разделены строго по типу платежей.
    # Проще показать баланс каждой кассы.
    # Если вы хотите общую сумму по наличным и картам, вам нужно будет либо
    # суммировать балансы касс, помеченных как is_default_for_cash/is_default_for_card,
    # либо анализировать все транзакции, что может быть медленно.
    # Пока что просто выведем балансы всех активных касс.

    context = {
        **admin.site.each_context(request), # Добавляем стандартный админский контекст
        'title': 'Отчет: Обзор кассы',
        'active_cash_registers': active_cash_registers,
        'recent_income_transactions': recent_income_transactions,
        'user_can_view_this_specific_report': True, # Право уже проверено
    }
    return render(request, 'admin/cash_register/cash_overview_report.html', context)