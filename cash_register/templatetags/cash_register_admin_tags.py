# F:\CRM 2.0\ERP\cash_register\templatetags\cash_register_admin_tags.py
from django import template
from ..models import CashRegister # Убедитесь, что путь импорта модели корректен

register = template.Library()

@register.inclusion_tag('admin/cash_register/includes/dashboard_cash_balances.html', takes_context=True)
def get_cash_register_balances(context):
    user = context.get('user') # Получаем текущего пользователя из контекста шаблона
    
    # Начинаем с выборки всех активных касс
    cash_registers_qs = CashRegister.objects.filter(is_active=True)

    # Если пользователь существует и не является суперпользователем, применяем фильтрацию
    if user and not user.is_superuser:
        user_groups = user.groups.all()
        if user_groups.exists(): # Фильтруем, только если пользователь состоит в каких-либо группах
            # Показываем только те кассы, которые явно разрешены для групп пользователя.
            # distinct() нужен на случай, если касса разрешена нескольким группам пользователя.
            cash_registers_qs = cash_registers_qs.filter(allowed_groups__in=user_groups).distinct()
        else:
            # Если пользователь (не суперпользователь) не состоит ни в одной группе, 
            # он не увидит кассы, доступ к которым ограничен группами.
            cash_registers_qs = cash_registers_qs.none() # Возвращаем пустой queryset
    
    # Для суперпользователя cash_registers_qs останется нефильтрованным по группам (покажет все активные).
    
    return {
        'cash_registers': cash_registers_qs.order_by('name'),
        # 'user': user # Переменная user уже есть в глобальном контексте админки, 
                       # ее не обязательно передавать снова явно в шаблон тега, если он ее не использует.
                       # Оставим на случай, если понадобится в dashboard_cash_balances.html
    }