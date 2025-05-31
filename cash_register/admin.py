# F:\CRM 2.0\ERP\cash_register\admin.py
from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils.html import format_html

from .models import ExpenseCategory, CashRegister, CashTransaction
from .forms import CashTransactionAdminForm, TransferFundsForm

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    ordering = ['name']

@admin.register(CashRegister)
class CashRegisterAdmin(admin.ModelAdmin):
    list_display = ('name', 'current_balance', 'is_active', 'till_type', 
                    'is_default_for_cash', 'is_default_for_card', 'display_allowed_groups')
    list_filter = ('is_active', 'till_type', 'is_default_for_cash', 'is_default_for_card', 'allowed_groups')
    search_fields = ('name',)
    readonly_fields = ('current_balance',)
    filter_horizontal = ('allowed_groups',)
    actions = ['initiate_transfer_funds_action']
    ordering = ['name']

    def display_allowed_groups(self, obj):
        return ", ".join([group.name for group in obj.allowed_groups.all()])
    display_allowed_groups.short_description = "Доступные группы"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(allowed_groups__in=request.user.groups.all()).distinct()

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser: return True
        if obj is not None:
            return obj.allowed_groups.filter(pk__in=request.user.groups.all()).exists() and \
                   request.user.has_perm('cash_register.view_cashregister')
        return request.user.has_perm('cash_register.view_cashregister')

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser: return True
        if obj is not None:
            return obj.allowed_groups.filter(pk__in=request.user.groups.all()).exists() and \
                   request.user.has_perm('cash_register.change_cashregister')
        return request.user.has_perm('cash_register.change_cashregister')
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:source_cash_register_id>/transfer/',
                self.admin_site.admin_view(self.transfer_funds_form_view),
                name='cash_register_cashregister_transfer_funds' 
            ),
        ]
        return custom_urls + urls

    def transfer_funds_form_view(self, request, source_cash_register_id):
        # ... (код transfer_funds_form_view как в turn 225/231/237) ...
        if not request.user.has_perm('cash_register.can_transfer_funds'): raise PermissionDenied("У вас нет прав для выполнения этой операции.")
        source_cr = get_object_or_404(CashRegister, pk=source_cash_register_id)
        if not request.user.is_superuser and not source_cr.allowed_groups.filter(pk__in=request.user.groups.all()).exists(): raise PermissionDenied("У вас нет прав на списание из этой кассы.")
        form = TransferFundsForm(request.POST or None, source_cash_register=source_cr)
        if request.method == 'POST':
            if form.is_valid():
                amount = form.cleaned_data['amount']; destination_cr = form.cleaned_data['destination_cash_register']; description = form.cleaned_data.get('description', '')
                try:
                    with transaction.atomic():
                        desc_out = f"Перемещение в кассу: {destination_cr.name}. {description}".strip(); t_out = CashTransaction.objects.create(cash_register=source_cr, transaction_type=CashTransaction.TRANSACTION_TYPE_TRANSFER_OUT, payment_method=CashTransaction.PAYMENT_METHOD_TRANSFER, amount=amount, employee=request.user, description=desc_out)
                        desc_in = f"Перемещение из кассы: {source_cr.name}. {description}".strip(); t_in = CashTransaction.objects.create(cash_register=destination_cr, transaction_type=CashTransaction.TRANSACTION_TYPE_TRANSFER_IN, payment_method=CashTransaction.PAYMENT_METHOD_TRANSFER, amount=amount, employee=request.user, description=desc_in)
                        t_out.paired_transfer_transaction = t_in; t_out.save(update_fields=['paired_transfer_transaction']); t_in.paired_transfer_transaction = t_out; t_in.save(update_fields=['paired_transfer_transaction'])
                        messages.success(request, f"Средства в размере {amount} руб. успешно перемещены из кассы '{source_cr.name}' в кассу '{destination_cr.name}'.")
                        return HttpResponseRedirect(reverse('admin:cash_register_cashregister_changelist'))
                except Exception as e: messages.error(request, f"Ошибка при выполнении перемещения: {e}")
        context = {**self.admin_site.each_context(request), 'title': f'Перемещение средств из кассы: {source_cr.name}', 'form': form, 'opts': self.model._meta, 'source_cash_register': source_cr, 'has_permission': request.user.has_perm('cash_register.can_transfer_funds')}
        return render(request, 'admin/cash_register/cashregister/transfer_funds_form.html', context)

    @admin.action(description='Переместить средства из выбранной кассы', permissions=['can_transfer_funds'])
    def initiate_transfer_funds_action(self, request, queryset):
        # ... (код initiate_transfer_funds_action как в turn 225/231/237) ...
        if queryset.count() != 1: self.message_user(request, "Пожалуйста, выберите только одну кассу-источник для перемещения.", messages.WARNING); return
        source_cr = queryset.first()
        if not request.user.is_superuser and not source_cr.allowed_groups.filter(pk__in=request.user.groups.all()).exists(): self.message_user(request, f"У вас нет прав на списание из кассы '{source_cr.name}'.", messages.ERROR); return
        return HttpResponseRedirect(reverse('admin:cash_register_cashregister_transfer_funds', args=[source_cr.id]))
    
    def has_can_transfer_funds_permission(self, request):
        return request.user.has_perm('cash_register.can_transfer_funds')


@admin.register(CashTransaction)
class CashTransactionAdmin(admin.ModelAdmin):
    form = CashTransactionAdminForm
    list_display = (
        'timestamp', 
        'display_transaction_type_styled', 
        'display_amount_styled',           
        'payment_method', 
        'display_cash_register_type', # <--- ИЗМЕНЕНО ЗДЕСЬ
        'order_link_for_list_display', 
        'expense_category',
        'display_paired_transfer', 
        'employee', 
        'description'
    )
    list_filter = ('timestamp', 'transaction_type', 'payment_method', 'cash_register__name', 'cash_register__till_type', 'employee', 'expense_category') # Добавил cash_register__till_type
    search_fields = ('order__id', 'description', 'employee__username', 
                     'expense_category__name', 'paired_transfer_transaction__id', 
                     'cash_register__name', 'cash_register__till_type') # Добавил cash_register__till_type
    list_select_related = ('cash_register', 'order', 'employee', 'expense_category', 'paired_transfer_transaction')
    ordering = ['-timestamp']

    def get_fields(self, request, obj=None):
        # Отображаем тип кассы вместо полного инфо на форме редактирования
        base_fields_change = ['timestamp', 'display_cash_register_type_form', 'transaction_type', 'payment_method', 'amount', 
                              'order_link_display', 'expense_category', 'paired_transfer_link_display', 
                              'employee', 'description']
        base_fields_add = ['cash_register', 'transaction_type', 'payment_method', 'amount', 
                           'expense_category', 'employee', 'description', 'order']
        if obj: 
            if obj.transaction_type == CashTransaction.TRANSACTION_TYPE_INCOME:
                current_fields_change = [f for f in base_fields_change if f != 'expense_category']
                return tuple(current_fields_change)
            return tuple(base_fields_change)
        return tuple(base_fields_add)

    def get_readonly_fields(self, request, obj=None):
        if obj: 
            base_readonly = ['timestamp', 'display_cash_register_type_form', 'transaction_type', # Используем новый метод
                             'payment_method', 'amount', 'order_link_display', 
                             'paired_transfer_link_display', 'employee', 'order']
            if obj.transaction_type == CashTransaction.TRANSACTION_TYPE_INCOME:
                base_readonly.append('expense_category')
            return tuple(set(base_readonly))
        return ()

    def has_add_permission(self, request): return True

    # ----- ИЗМЕНЯЕМ МЕТОДЫ ОТОБРАЖЕНИЯ КАССЫ -----
    # Метод для формы редактирования (в get_fields/readonly_fields)
    def display_cash_register_type_form(self, obj):
        if obj.cash_register:
            return obj.cash_register.get_till_type_display() # Только тип
        return "-"
    display_cash_register_type_form.short_description = "Касса (Тип)"

    # Метод для списка (list_display)
    def display_cash_register_type(self, obj):
        if obj.cash_register:
            return obj.cash_register.get_till_type_display() # Только тип
        return "-"
    display_cash_register_type.short_description = "Касса (Тип)" # Название колонки
    display_cash_register_type.admin_order_field = 'cash_register__till_type' # Для сортировки по типу кассы
    # ----- КОНЕЦ ИЗМЕНЕНИЙ МЕТОДОВ ОТОБРАЖЕНИЯ КАССЫ -----

    # Остальные кастомные методы отображения остаются как были
    def order_link_display(self, obj):
        if obj.order: link = reverse("admin:orders_order_change", args=[obj.order.id]); return format_html('<a href="{}">Заказ №{}</a>', link, obj.order.id)
        return "-"
    order_link_display.short_description = "Связанный заказ" # Это для формы, если используется
    
    def order_link_for_list_display(self, obj): 
        return self.order_link_display(obj)
    order_link_for_list_display.short_description = "Заказ"

    def display_transaction_type_styled(self, obj):
        ttype = obj.get_transaction_type_display()
        color = 'inherit'
        if obj.transaction_type in [CashTransaction.TRANSACTION_TYPE_EXPENSE, CashTransaction.TRANSACTION_TYPE_TRANSFER_OUT]: color = 'red'
        elif obj.transaction_type in [CashTransaction.TRANSACTION_TYPE_INCOME, CashTransaction.TRANSACTION_TYPE_TRANSFER_IN]: color = 'green'
        return format_html('<span style="color: {};">{}</span>', color, ttype)
    display_transaction_type_styled.short_description = 'Тип транзакции'; display_transaction_type_styled.admin_order_field = 'transaction_type'

    def display_amount_styled(self, obj):
        sign = ""
        color = 'inherit'
        if obj.transaction_type in [CashTransaction.TRANSACTION_TYPE_EXPENSE, CashTransaction.TRANSACTION_TYPE_TRANSFER_OUT]: sign = "-"; color = 'red'
        elif obj.transaction_type in [CashTransaction.TRANSACTION_TYPE_INCOME, CashTransaction.TRANSACTION_TYPE_TRANSFER_IN]: sign = "+"; color = 'green'
        return format_html('<span style="color: {};">{}{}</span>', color, sign, obj.amount)
    display_amount_styled.short_description = 'Сумма'; display_amount_styled.admin_order_field = 'amount'
    
    def display_paired_transfer(self, obj):
        if obj.paired_transfer_transaction:
            link = reverse("admin:cash_register_cashtransaction_change", args=[obj.paired_transfer_transaction.id])
            return format_html('<a href="{}">Транз. №{} ({})</a>', link, obj.paired_transfer_transaction.id, obj.paired_transfer_transaction.cash_register.name)
        return "-"
    display_paired_transfer.short_description = "Парная операция"

    def paired_transfer_link_display(self, obj): 
        return self.display_paired_transfer(obj)
    paired_transfer_link_display.short_description = "Парная операция перемещения"

    class Media:
        js = ('cash_register/js/transaction_form.js',)