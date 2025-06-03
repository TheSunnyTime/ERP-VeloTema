# F:\CRM 2.0\ERP\cash_register\admin.py
from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils.html import format_html
# from django.db.models import Q # Оставим, если понадобится

from .models import ExpenseCategory, CashRegister, CashTransaction
from .forms import CashTransactionAdminForm, TransferFundsForm # TransferFundsForm нам понадобится позже

# --- НАСТРОЙКА ---
# Замени "ИМЯ_ТВОЕЙ_ГРУППЫ_С_ОГРАНИЧЕННЫМ_ДОСТУПОМ_К_ГКО" 
# на реальное имя твоей группы пользователей, для которой нужно скрывать ГКО.
GROUP_NO_GKO_ACCESS = "ИМЯ_ТВОЕЙ_ГРУППЫ_С_ОГРАНИЧЕННЫМ_ДОСТУПОМ_К_ГКО" 
# Например: GROUP_NO_GKO_ACCESS = "Операторы ТТ"

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

        user_groups = request.user.groups.all()
        # 1. Фильтруем по allowed_groups (существующая логика)
        current_qs = qs.filter(allowed_groups__in=user_groups).distinct()

        # 2. Если пользователь в группе GROUP_NO_GKO_ACCESS, дополнительно скрываем ГКО
        if user_groups.filter(name=GROUP_NO_GKO_ACCESS).exists():
            current_qs = current_qs.exclude(till_type=CashRegister.TYPE_MAIN_ORGANIZATION)
        
        return current_qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Применяем логику ко всем ForeignKey полям, ссылающимся на CashRegister
        if db_field.related_model == CashRegister:
            # Начинаем с полного queryset или с того, что уже было передано
            current_queryset = kwargs.get('queryset', CashRegister.objects.all())

            if not request.user.is_superuser:
                user_groups = request.user.groups.all()
                # Фильтр по allowed_groups
                current_queryset = current_queryset.filter(allowed_groups__in=user_groups).distinct()

                # Если пользователь в ограниченной группе, исключаем ГКО
                # При выборе кассы (например, для транзакции или перевода) пользователь из этой группы
                # не должен иметь возможности выбрать ГКО, независимо от права can_view_gko_cash_transactions
                # (т.к. это право на просмотр транзакций, а не на операции с кассой ГКО).
                if user_groups.filter(name=GROUP_NO_GKO_ACCESS).exists():
                    current_queryset = current_queryset.exclude(till_type=CashRegister.TYPE_MAIN_ORGANIZATION)
            
            kwargs['queryset'] = current_queryset
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # Усиление проверки прав для просмотра/изменения конкретного объекта ГКО
    def _is_user_restricted_for_gko(self, user):
        if user.is_superuser:
            return False
        return user.groups.filter(name=GROUP_NO_GKO_ACCESS).exists()

    def has_view_permission(self, request, obj=None):
        # Базовая проверка Django (учитывает пермишн 'cash_register.view_cashregister')
        base_perm = super().has_view_permission(request, obj)
        if not base_perm:
            return False
        
        if request.user.is_superuser:
            return True

        if obj is not None:
            # Проверяем allowed_groups (твоя существующая логика)
            can_view_based_on_allowed_groups = obj.allowed_groups.filter(pk__in=request.user.groups.all()).exists()
            if not can_view_based_on_allowed_groups:
                return False
            
            # Если это ГКО и пользователь в ограниченной группе, запрещаем просмотр
            if obj.till_type == CashRegister.TYPE_MAIN_ORGANIZATION and self._is_user_restricted_for_gko(request.user):
                return False # Явно запрещаем, если это ГКО и пользователь ограничен
        
        # Для доступа к списку (obj is None) - get_queryset уже отфильтрует.
        # Для отдельных объектов - вышестоящие проверки ужесточили доступ.
        return True


    def has_change_permission(self, request, obj=None):
        base_perm = super().has_change_permission(request, obj)
        if not base_perm:
            return False

        if request.user.is_superuser:
            return True
            
        if obj is not None:
            can_change_based_on_allowed_groups = obj.allowed_groups.filter(pk__in=request.user.groups.all()).exists()
            if not can_change_based_on_allowed_groups:
                return False

            if obj.till_type == CashRegister.TYPE_MAIN_ORGANIZATION and self._is_user_restricted_for_gko(request.user):
                return False # Запрещаем изменение ГКО, если пользователь ограничен
        return True
    
    def get_urls(self): # Твой код
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
        if not request.user.has_perm('cash_register.can_transfer_funds'): 
            raise PermissionDenied("У вас нет прав для выполнения этой операции.")
        
        source_cr = get_object_or_404(CashRegister, pk=source_cash_register_id)

        # Проверка доступа к исходной кассе (allowed_groups)
        if not request.user.is_superuser and not source_cr.allowed_groups.filter(pk__in=request.user.groups.all()).exists():
            raise PermissionDenied("У вас нет прав на операции с исходной кассой.")

        # Запрет на использование ГКО как ИСТОЧНИКА для ограниченной группы
        if source_cr.till_type == CashRegister.TYPE_MAIN_ORGANIZATION and self._is_user_restricted_for_gko(request.user):
            messages.error(request, f"Операции из кассы '{source_cr.name}' (ГКО) запрещены для вашей группы.")
            return HttpResponseRedirect(reverse('admin:cash_register_cashregister_changelist'))

        # Передаем request в форму, чтобы она могла фильтровать кассы назначения
        form = TransferFundsForm(request.POST or None, source_cash_register=source_cr, request_user=request.user)
        
        if request.method == 'POST':
            if form.is_valid():
                amount = form.cleaned_data['amount']
                destination_cr = form.cleaned_data['destination_cash_register'] # Форма уже должна отфильтровать это поле
                description = form.cleaned_data.get('description', '')
                
                # Дополнительная серверная проверка (на случай, если JS обошли или форма не справилась)
                # Эта проверка дублирует то, что должно быть в форме, но для безопасности.
                if destination_cr.till_type == CashRegister.TYPE_MAIN_ORGANIZATION and self._is_user_restricted_for_gko(request.user):
                    messages.error(request, f"Касса '{destination_cr.name}' (ГКО) не может быть выбрана как касса назначения для вашей группы.")
                else:
                    try:
                        with transaction.atomic():
                            desc_out = f"Перемещение в кассу: {destination_cr.name}. {description}".strip()
                            t_out = CashTransaction.objects.create(
                                cash_register=source_cr, 
                                transaction_type=CashTransaction.TRANSACTION_TYPE_TRANSFER_OUT, 
                                payment_method=CashTransaction.PAYMENT_METHOD_TRANSFER, 
                                amount=amount, employee=request.user, description=desc_out
                            )
                            desc_in = f"Перемещение из кассы: {source_cr.name}. {description}".strip()
                            t_in = CashTransaction.objects.create(
                                cash_register=destination_cr, 
                                transaction_type=CashTransaction.TRANSACTION_TYPE_TRANSFER_IN, 
                                payment_method=CashTransaction.PAYMENT_METHOD_TRANSFER, 
                                amount=amount, employee=request.user, description=desc_in
                            )
                            t_out.paired_transfer_transaction = t_in
                            t_out.save(update_fields=['paired_transfer_transaction'])
                            t_in.paired_transfer_transaction = t_out
                            t_in.save(update_fields=['paired_transfer_transaction'])
                            messages.success(request, f"Средства в размере {amount} руб. успешно перемещены из кассы '{source_cr.name}' в кассу '{destination_cr.name}'.")
                            return HttpResponseRedirect(reverse('admin:cash_register_cashregister_changelist'))
                    except Exception as e:
                        messages.error(request, f"Ошибка при выполнении перемещения: {e}")
        
        context = {
            **self.admin_site.each_context(request), 
            'title': f'Перемещение средств из кассы: {source_cr.name}', 
            'form': form, 
            'opts': self.model._meta, 
            'source_cash_register': source_cr, 
            'has_permission': request.user.has_perm('cash_register.can_transfer_funds')
        }
        return render(request, 'admin/cash_register/cashregister/transfer_funds_form.html', context)

    @admin.action(description='Переместить средства из выбранной кассы', permissions=['can_transfer_funds'])
    def initiate_transfer_funds_action(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Пожалуйста, выберите только одну кассу-источник для перемещения.", messages.WARNING)
            return
        
        source_cr = queryset.first()
        
        if not request.user.is_superuser and not source_cr.allowed_groups.filter(pk__in=request.user.groups.all()).exists():
            self.message_user(request, f"У вас нет прав на операции с кассой '{source_cr.name}'.", messages.ERROR)
            return

        if source_cr.till_type == CashRegister.TYPE_MAIN_ORGANIZATION and self._is_user_restricted_for_gko(request.user):
            self.message_user(request, f"Операции из кассы '{source_cr.name}' (ГКО) запрещены для вашей группы.", messages.ERROR)
            return
            
        return HttpResponseRedirect(reverse('admin:cash_register_cashregister_transfer_funds', args=[source_cr.id]))
    
    def has_can_transfer_funds_permission(self, request): # Твой код
        return request.user.has_perm('cash_register.can_transfer_funds')


@admin.register(CashTransaction)
class CashTransactionAdmin(admin.ModelAdmin):
    form = CashTransactionAdminForm
    list_display = (
        'timestamp', 
        'display_transaction_type_styled', 
        'display_amount_styled',          
        'payment_method', 
        'display_cash_register_type', 
        'order_link_for_list_display', 
        'expense_category',
        'display_paired_transfer', 
        'employee', 
        'description'
    )
    list_filter = ('timestamp', 'transaction_type', 'payment_method', 'cash_register__name', 'cash_register__till_type', 'employee', 'expense_category')
    search_fields = ('order__id', 'description', 'employee__username', 
                     'expense_category__name', 'paired_transfer_transaction__id', 
                     'cash_register__name', 'cash_register__till_type')
    list_select_related = ('cash_register', 'order', 'employee', 'expense_category', 'paired_transfer_transaction')
    ordering = ['-timestamp']

    def _is_user_restricted_for_gko(self, user): # Вспомогательный метод
        if user.is_superuser:
            return False
        return user.groups.filter(name=GROUP_NO_GKO_ACCESS).exists()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        user_can_view_gko_transactions = request.user.has_perm('cash_register.can_view_gko_cash_transactions')
        
        # 1. Определяем, какие кассы ВООБЩЕ доступны пользователю (через allowed_groups)
        visible_cr_qs = CashRegister.objects.filter(allowed_groups__in=request.user.groups.all()).distinct()

        # 2. Если пользователь в ограниченной группе И НЕ имеет права на просмотр транзакций ГКО,
        #    то из списка доступных ему касс мы дополнительно исключаем ГКО.
        if self._is_user_restricted_for_gko(request.user) and not user_can_view_gko_transactions:
            visible_cr_qs = visible_cr_qs.exclude(till_type=CashRegister.TYPE_MAIN_ORGANIZATION)
        
        # 3. Фильтруем транзакции по этому финальному списку доступных касс
        return qs.filter(cash_register__in=visible_cr_qs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "cash_register":
            # При создании/редактировании транзакции, какие кассы можно выбрать?
            current_queryset = CashRegister.objects.all()
            if not request.user.is_superuser:
                user_groups = request.user.groups.all()
                current_queryset = current_queryset.filter(allowed_groups__in=user_groups).distinct()
                
                # Ограниченная группа не может выбирать ГКО для создания транзакций,
                # даже если у них есть право can_view_gko_cash_transactions (это право на ПРОСМОТР).
                if user_groups.filter(name=GROUP_NO_GKO_ACCESS).exists():
                    current_queryset = current_queryset.exclude(till_type=CashRegister.TYPE_MAIN_ORGANIZATION)
            kwargs['queryset'] = current_queryset
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # ... (остальные твои методы display_... и Media без изменений) ...
    def get_fields(self, request, obj=None): # Твой код
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

    def get_readonly_fields(self, request, obj=None): # Твой код
        if obj: 
            base_readonly = ['timestamp', 'display_cash_register_type_form', 'transaction_type', 
                             'payment_method', 'amount', 'order_link_display', 
                             'paired_transfer_link_display', 'employee', 'order']
            if obj.transaction_type == CashTransaction.TRANSACTION_TYPE_INCOME:
                base_readonly.append('expense_category')
            return tuple(set(base_readonly))
        return ()

    def has_add_permission(self, request): return True # Твой код

    def display_cash_register_type_form(self, obj): # Твой код
        if obj.cash_register: return obj.cash_register.get_till_type_display()
        return "-"
    display_cash_register_type_form.short_description = "Касса (Тип)"

    def display_cash_register_type(self, obj): # Твой код
        if obj.cash_register: return obj.cash_register.get_till_type_display()
        return "-"
    display_cash_register_type.short_description = "Касса (Тип)"; display_cash_register_type.admin_order_field = 'cash_register__till_type'
    
    def order_link_display(self, obj): # Твой код
        if obj.order: link = reverse("admin:orders_order_change", args=[obj.order.id]); return format_html('<a href="{}">Заказ №{}</a>', link, obj.order.id)
        return "-"
    order_link_display.short_description = "Связанный заказ"
    
    def order_link_for_list_display(self, obj):  # Твой код
        return self.order_link_display(obj)
    order_link_for_list_display.short_description = "Заказ"

    def display_transaction_type_styled(self, obj): # Твой код
        ttype = obj.get_transaction_type_display(); color = 'inherit'
        if obj.transaction_type in [CashTransaction.TRANSACTION_TYPE_EXPENSE, CashTransaction.TRANSACTION_TYPE_TRANSFER_OUT]: color = 'red'
        elif obj.transaction_type in [CashTransaction.TRANSACTION_TYPE_INCOME, CashTransaction.TRANSACTION_TYPE_TRANSFER_IN]: color = 'green'
        return format_html('<span style="color: {};">{}</span>', color, ttype)
    display_transaction_type_styled.short_description = 'Тип транзакции'; display_transaction_type_styled.admin_order_field = 'transaction_type'

    def display_amount_styled(self, obj): # Твой код
        sign = ""; color = 'inherit'
        if obj.transaction_type in [CashTransaction.TRANSACTION_TYPE_EXPENSE, CashTransaction.TRANSACTION_TYPE_TRANSFER_OUT]: sign = "-"; color = 'red'
        elif obj.transaction_type in [CashTransaction.TRANSACTION_TYPE_INCOME, CashTransaction.TRANSACTION_TYPE_TRANSFER_IN]: sign = "+"; color = 'green'
        return format_html('<span style="color: {};">{}{}</span>', color, sign, obj.amount)
    display_amount_styled.short_description = 'Сумма'; display_amount_styled.admin_order_field = 'amount'
    
    def display_paired_transfer(self, obj): # Твой код
        if obj.paired_transfer_transaction:
            link = reverse("admin:cash_register_cashtransaction_change", args=[obj.paired_transfer_transaction.id])
            return format_html('<a href="{}">Транз. №{} ({})</a>', link, obj.paired_transfer_transaction.id, obj.paired_transfer_transaction.cash_register.name) # Исправлено: был obj.paired_transfer_transaction.cash_register__name
        return "-"
    display_paired_transfer.short_description = "Парная операция"

    def paired_transfer_link_display(self, obj): # Твой код
        return self.display_paired_transfer(obj)
    paired_transfer_link_display.short_description = "Парная операция перемещения"

    class Media: # Твой код
        js = ('cash_register/js/transaction_form.js',)