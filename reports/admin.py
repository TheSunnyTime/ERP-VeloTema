# F:\CRM 2.0\ERP\reports\admin.py
from django.contrib import admin
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.core.exceptions import PermissionDenied
from .models import ReportAccessPermission, ExpenseReportProxy 
from django.contrib import messages # messages здесь не используются, можно убрать

# Импортируем ТОЛЬКО те модели, которые определены в reports.models
from .models import (
    ReportAccessPermission, 
    StockSummaryReportProxy, 
    EmployeeSalaryReportProxy,
    AllEmployeesSalaryReportProxy # Оставим импорт здесь, если модель определена в reports.models
                                  # Но ее админ-класс будет в salary_management.admin.py
)
# НЕ НУЖНО импортировать сюда EmployeeRate, SalaryCalculation и т.д. из salary_management

@admin.register(ReportAccessPermission)
class ReportAccessPermissionAdmin(admin.ModelAdmin):
    # Оставляем твою логику для этого класса, она выглядит нормально,
    # если ты хочешь, чтобы только суперпользователь управлял этими "пустыми" правами.
    # Однако, обычно права создаются миграциями и назначаются группам/пользователям,
    # а не управляются через такую модель в админке.
    # Но если это твой специальный механизм, то оставляем.
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    def has_view_permission(self, request, obj=None): return request.user.is_superuser
    def has_module_permission(self, request): return request.user.is_superuser

@admin.register(StockSummaryReportProxy)
class StockSummaryReportProxyAdmin(admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        # Убедись, что право 'reports.view_stock_summary_report' определено в ReportAccessPermission.Meta.permissions
        if not request.user.has_perm('reports.view_stock_summary_report') and not request.user.is_superuser:
            raise PermissionDenied("У тебя нет прав для просмотра этого отчета.")
        
        try:
            report_url = reverse('reports:stock_summary_report')
        except Exception as e:
            messages.error(request, f"Ошибка: URL для отчета 'Сводный отчет по остаткам' не настроен ({e}). Проверьте reports.urls.")
            return HttpResponseRedirect(reverse('admin:index'))
        return HttpResponseRedirect(report_url)

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    
    def has_module_permission(self, request):
        if request.user.is_superuser: return True
        return request.user.has_perm('reports.view_stock_summary_report')

    def has_view_permission(self, request, obj=None): # Для возможности кликнуть по ссылке
        if request.user.is_superuser: return True
        return request.user.has_perm('reports.view_stock_summary_report')

@admin.register(EmployeeSalaryReportProxy)
class EmployeeSalaryReportProxyAdmin(admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        if not request.user.is_authenticated: # Простая проверка на аутентификацию для личного отчета
            raise PermissionDenied("Доступ запрещен. Пожалуйста, войдите в систему.")
        
        try:
            # Этот отчет, судя по 'utils:my_salary_report', находится в приложении utils
            report_url = reverse('utils:my_salary_report') 
        except Exception as e:
            messages.error(request, f"Ошибка: URL для отчета 'Мой отчет по зарплате' не настроен ({e}). Проверьте utils.urls.")
            return HttpResponseRedirect(reverse('admin:index'))
        return HttpResponseRedirect(report_url)

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

    def has_module_permission(self, request): # Кто видит эту ссылку в разделе "Reports"
        return request.user.is_authenticated 

    def has_view_permission(self, request, obj=None): # Кто может нажать на ссылку
        return request.user.is_authenticated

# -------------------------------------------------------------------------------------
# КЛАСС AllEmployeesSalaryReportProxyAdmin БЫЛ ЗДЕСЬ, НО МЫ ПЕРЕМЕСТИЛИ ЕГО РЕГИСТРАЦИЮ
# В salary_management/admin.py, ПОТОМУ ЧТО В МОДЕЛИ AllEmployeesSalaryReportProxy
# ТЫ УКАЗАЛ app_label = 'salary_management'
# -------------------------------------------------------------------------------------
@admin.register(ExpenseReportProxy)
class ExpenseReportProxyAdmin(admin.ModelAdmin):
    # Этот класс регистрирует нашу прокси-модель в админке.
    # Мы не хотим отображать для нее стандартный список объектов (changelist),
    # а хотим сразу перенаправлять на страницу отчета.

    def changelist_view(self, request, extra_context=None):
        # Перенаправляем пользователя на кастомную страницу отчета по расходам.
        # Используем пространство имен 'custom_reports_admin', которое ты задал в ERP/urls.py
        return HttpResponseRedirect(reverse('custom_reports_admin:expense_report'))

    def has_add_permission(self, request):
        # Запрещаем добавление объектов через эту прокси-модель
        return False

    def has_change_permission(self, request, obj=None):
        # Запрещаем изменение объектов через эту прокси-модель
        return False

    def has_delete_permission(self, request, obj=None):
        # Запрещаем удаление объектов через эту прокси-модель
        return False

    def has_view_permission(self, request, obj=None):
        # Право на просмотр самой "модели" (т.е. ссылки на отчет) в списке.
        # Если нет этого права, пользователь даже не увидит ссылку на отчет.
        # Это дублирует has_module_permission, но может быть полезно для более гранулярного контроля,
        # если бы у прокси-модели была своя страница деталей (чего у нас нет).
        # В нашем случае, основной контроль видимости раздела будет через has_module_permission.
        return request.user.has_perm('reports.view_expense_report') or request.user.is_superuser

    def has_module_permission(self, request):
        # Определяет, будет ли вообще показан этот "модуль" (наша прокси-модель/ссылка на отчет)
        # в списке приложений на главной странице админки или в навигации.
        if request.user.is_superuser:
            return True
        return request.user.has_perm('reports.view_expense_report')

# Пример регистрации других твоих прокси-моделей отчетов, если они еще не зарегистрированы
# или если ты хочешь привести их к похожему виду (с редиректом и проверкой прав).
# Убедись, что для них также есть соответствующие URL и права.

# from .models import StockSummaryReportProxy
# @admin.register(StockSummaryReportProxy)
# class StockSummaryReportProxyAdmin(admin.ModelAdmin):
#     def changelist_view(self, request, extra_context=None):
#         return HttpResponseRedirect(reverse('custom_reports_admin:stock_summary_report')) # Пример
#
#     def has_module_permission(self, request):
#         if request.user.is_superuser:
#             return True
#         return request.user.has_perm('reports.view_stock_summary_report') # Убедись, что право существует
#
#     # Также добавь has_add_permission, has_change_permission, has_delete_permission, возвращающие False
