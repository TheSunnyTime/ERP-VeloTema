# salary_management/admin.py
from django.contrib import admin
from django.db.models import F, Max # Импортируем Max для получения процента
from decimal import Decimal # Импортируем Decimal
from django.urls import reverse # Добавь, если еще нет
from django.http import HttpResponseRedirect # Добавь, если еще нет
from django.core.exceptions import PermissionDenied # Добавь, если еще нет
from django.contrib import messages # Добавь, если еще нет

from reports.models import AllEmployeesSalaryReportProxy #
from .models import (
    EmployeeRate, 
    SalaryCalculation, 
    SalaryPayment, 
    SalaryCalculationDetail, 
    ProductSalaryDetail 
)

@admin.register(EmployeeRate)
class EmployeeRateAdmin(admin.ModelAdmin):
    # ... (твой код для EmployeeRateAdmin) ...
    list_display = (
        'employee', 
        'order_type', 
        'role_in_order',
        'service_percentage', 
        'product_profit_percentage',
        'is_active', 
        'notes', 
        'updated_at'
    )
    list_filter = ('is_active', 'employee', 'order_type', 'role_in_order')
    search_fields = ('employee__username', 'employee__first_name', 'order_type__name')
    autocomplete_fields = ('employee', 'order_type')
    list_editable = ('service_percentage', 'product_profit_percentage', 'is_active')
    ordering = ('employee__username', 'order_type__name', 'role_in_order')
    fields = (
        'employee', 
        'order_type', 
        'role_in_order',
        'service_percentage', 
        'product_profit_percentage',
        'is_active',
        'notes',
        ('created_at', 'updated_at')
    )
    readonly_fields = ('created_at', 'updated_at')

# --- СНАЧАЛА ОПРЕДЕЛЯЕМ ВСЕ ИНЛАЙНЫ ---

class SalaryCalculationDetailInline(admin.TabularInline):
    model = SalaryCalculationDetail
    extra = 0 
    fields = ('order_service_item', 'source_description', 'base_amount_for_calc', 
              'applied_percentage', 'earned_amount', 'detail_type', 'created_at')
    readonly_fields = ('created_at',)
    # autocomplete_fields = ['order_service_item'] # Если нужно

class ProductSalaryDetailInline(admin.TabularInline):
    model = ProductSalaryDetail
    extra = 0
    fields = ('order_product_item', 'product_name_snapshot', 'product_price_at_sale', 
              'product_cost_at_sale', 'profit_from_item', 'applied_percentage', 
              'earned_amount', 'created_at')
    readonly_fields = ('product_name_snapshot', 'product_price_at_sale', 
                       'product_cost_at_sale', 'profit_from_item', 'created_at')
    # autocomplete_fields = ['order_product_item'] # Если нужно
    
    def has_add_permission(self, request, obj=None):
        return False 
    def has_delete_permission(self, request, obj=None):
        return False
    # def has_change_permission(self, request, obj=None): # По умолчанию True, что позволяет просмотр
    #     return True

# --- ТЕПЕРЬ РЕГИСТРИРУЕМ SalaryCalculationAdmin И ИСПОЛЬЗУЕМ ИНЛАЙНЫ ---

@admin.register(SalaryCalculation)
class SalaryCalculationAdmin(admin.ModelAdmin):
    list_display = (
        'employee', 
        'order', 
        # 'role_context', # Заменяем это на новый метод
        'display_role_context_with_rates', # <--- НАШ НОВЫЙ МЕТОД ОТОБРАЖЕНИЯ
        'total_calculated_amount', 
        'period_date', 
        'calculation_type',
        'created_at'
    )
    list_filter = (
        'employee', 
        'period_date', 
        'calculation_type', 
        'role_context', # Фильтр по самому полю role_context оставляем
        'order__order_type'
    )
    search_fields = (
        'employee__username', 
        'employee__first_name', 
        'order__id', 
        'applied_base_rule_info',
        'role_context'
    )
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('employee', 'order')

    fieldsets = (
        (None, {'fields': ('employee', 'order', 'role_context', 'period_date')}),
        ('Детали расчета', {'fields': ('total_calculated_amount', 'calculation_type', 'applied_base_rule_info')}),
        ('Информация о записи', {'fields': (('created_at', 'updated_at'),), 'classes': ('collapse',)}),
    )
    
    inlines = [
        SalaryCalculationDetailInline,
        ProductSalaryDetailInline
    ]

    # --- НОВЫЙ МЕТОД ДЛЯ list_display ---
    def display_role_context_with_rates(self, obj):
        role_display_text = obj.get_role_context_display() # "Начисление как Менеджеру" и т.д.
        
        applied_rates_parts = []

        # Проверяем детали по услугам
        # Берем процент из первой попавшейся детали с начислением (он должен быть одинаков для всех деталей услуг в этом расчете)
        first_service_detail_with_earning = obj.service_details.filter(earned_amount__gt=Decimal('0.00')).first()
        if first_service_detail_with_earning:
            # Убедимся, что у детали есть поле applied_percentage
            if hasattr(first_service_detail_with_earning, 'applied_percentage'):
                 applied_rates_parts.append(f"{first_service_detail_with_earning.applied_percentage}% (услуги)")

        # Проверяем детали по прибыли товаров
        first_product_detail_with_earning = obj.product_profit_details.filter(earned_amount__gt=Decimal('0.00')).first()
        if first_product_detail_with_earning:
            if hasattr(first_product_detail_with_earning, 'applied_percentage'):
                applied_rates_parts.append(f"{first_product_detail_with_earning.applied_percentage}% (приб.тов.)")
        
        if applied_rates_parts:
            return f"{role_display_text} [{'; '.join(applied_rates_parts)}]"
        else:
            # Если начислений по деталям нет, но total_calculated_amount > 0 (например, ручное начисление в будущем)
            # или просто хотим показать роль
            if obj.total_calculated_amount == Decimal('0.00'):
                 return f"{role_display_text} [Без % или начислений]"
            else:
                 return role_display_text # Просто роль, если нет деталей с процентами

    display_role_context_with_rates.short_description = "Контекст роли и ставки"
    # display_role_context_with_rates.admin_order_field = 'role_context' # Для сортировки по исходному полю роли
    # --- КОНЕЦ НОВОГО МЕТОДА ---

@admin.register(SalaryPayment)
class SalaryPaymentAdmin(admin.ModelAdmin):
    # ... (твой код для SalaryPaymentAdmin) ...
    list_display = ('employee', 'payment_date', 'amount_paid', 'payment_for_year', 'payment_for_month', 'created_by', 'created_at')
    list_filter = ('employee', 'payment_date', 'payment_for_year', 'payment_for_month', 'created_by')
    search_fields = ('employee__username', 'employee__first_name', 'notes')
    autocomplete_fields = ('employee', 'created_by')
    readonly_fields = ('created_at',)
    fieldsets = (
        (None, {'fields': ('employee', 'payment_date', 'amount_paid')}),
        ('Период выплаты', {'fields': ('payment_for_year', 'payment_for_month')}),
        ('Дополнительно', {'fields': ('notes',)}),
        ('Информация о записи', {'fields': ('created_by', 'created_at',)}),
    )
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
@admin.register(AllEmployeesSalaryReportProxy)
class AllEmployeesSalaryReportProxyAdmin(admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        required_permission = 'reports.view_all_employee_salaries' 
        if not request.user.is_superuser and not request.user.has_perm(required_permission):
            # Вместо PermissionDenied можно просто не показывать ссылку, если has_module_permission отработает
            messages.error(request, "У тебя нет прав для просмотра этого отчета.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('admin:index')))

        try:
            report_url = reverse('reports:all_employees_salary_report') 
        except Exception as e:
            messages.error(request, f"Ошибка: URL для отчета 'Сводный отчет по зарплате' не настроен ({e}). Проверьте reports.urls.")
            return HttpResponseRedirect(reverse('admin:index')) 
        return HttpResponseRedirect(report_url)

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

    def has_module_permission(self, request):
        if request.user.is_superuser: return True
        return request.user.has_perm('reports.view_all_employee_salaries') 

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser: return True
        return request.user.has_perm('reports.view_all_employee_salaries')