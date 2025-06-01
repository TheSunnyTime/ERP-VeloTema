# F:\CRM 2.0\ERP\reports\admin.py
from django.contrib import admin
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.core.exceptions import PermissionDenied
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