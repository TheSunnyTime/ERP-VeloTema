# F:\CRM 2.0\ERP\reports\admin.py
from django.contrib import admin
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.core.exceptions import PermissionDenied
# Убедись, что AllEmployeesSalaryReportProxy УДАЛЕН из этого импорта:
from .models import ReportAccessPermission, StockSummaryReportProxy, EmployeeSalaryReportProxy
# from .views import stock_summary_report # Если используется напрямую (у нас через reverse)

@admin.register(ReportAccessPermission)
class ReportAccessPermissionAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    def has_view_permission(self, request, obj=None): return request.user.is_superuser
    def has_module_permission(self, request): return request.user.is_superuser

@admin.register(StockSummaryReportProxy)
class StockSummaryReportProxyAdmin(admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        if not request.user.has_perm('reports.view_stock_summary_report'):
            raise PermissionDenied("У тебя нет прав для просмотра этого отчета.")
        report_url = reverse('reports:stock_summary_report')
        return HttpResponseRedirect(report_url)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    def has_view_permission(self, request, obj=None):
        return request.user.has_perm('reports.view_stock_summary_report') or request.user.is_superuser
    def has_module_permission(self, request):
        return request.user.has_perm('reports.view_stock_summary_report') or request.user.is_superuser

@admin.register(EmployeeSalaryReportProxy)
class EmployeeSalaryReportProxyAdmin(admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        if not request.user.is_authenticated: 
            raise PermissionDenied("Доступ запрещен.")
        report_url = reverse('utils:my_salary_report')
        return HttpResponseRedirect(report_url)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    def has_view_permission(self, request, obj=None):
        return request.user.is_authenticated
    def has_module_permission(self, request):
        return request.user.is_authenticated

# --- РЕГИСТРАЦИЯ AllEmployeesSalaryReportProxyAdmin УДАЛЕНА ОТСЮДА ---