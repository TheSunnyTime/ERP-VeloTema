# tasks/admin.py
from django import forms
from django.contrib import admin
from .models import TaskStatus, TaskType, Task # Убедись, что TaskType импортирован, если используется в get_fieldsets

class TaskAdminForm(forms.ModelForm): # <--- НОВАЯ ФОРМА
    class Meta:
        model = Task
        fields = '__all__' # Включаем все поля модели в форму

@admin.register(TaskStatus)
class TaskStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'order_in_list', 'is_final', 'description')
    list_editable = ('order_in_list', 'is_final')
    search_fields = ('name', 'description')
    list_filter = ('is_final',)
    ordering = ('order_in_list', 'name')

@admin.register(TaskType)
class TaskTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'get_default_visibility_groups')
    search_fields = ('name', 'description')
    filter_horizontal = ('default_visibility_groups',) # Удобный виджет для ManyToMany

    def get_default_visibility_groups(self, obj):
        return ", ".join([g.name for g in obj.default_visibility_groups.all()])
    get_default_visibility_groups.short_description = "Группы с авто-видимостью"


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    form = TaskAdminForm
    list_display = (
        'title', 
        'task_type', 
        'status', 
        'priority', 
        'assigned_to_user_display', 
        'assigned_to_group_display',
        'due_date', 
        'created_at',
        'related_object_link' 
    )
    list_filter = (
        'status', 
        'task_type', 
        'priority', 
        'assigned_to_user', 
        'assigned_to_group', 
        'due_date',
        'created_at'
    )
    search_fields = (
        'title', 
        'description', 
        'assigned_to_user__username', 
        'assigned_to_user__first_name', 
        'assigned_to_user__last_name',
        'assigned_to_group__name'
    )
    ordering = ('-priority', '-created_at')
    
    list_editable = ('status', 'priority') 

    fieldsets = (
        (None, {
            'fields': ('title', 'description')
        }),
        ('Детали задачи', {
            'fields': ('task_type', 'status', 'priority', 'due_date')
        }),
        ('Назначение', {
            'fields': ('assigned_to_user', 'assigned_to_group')
        }),
        ('Связанный объект (Опционально)', {
            'classes': ('collapse',), 
            'fields': ('content_type', 'object_id')
        }),
        ('Параметры для "Оплаты поставки"', { # Эта секция теперь будет видна всегда
            'classes': ('collapse',), 
            'fields': ('payment_cash_register_for_supply',)
        }),
        ('Информация о задаче', {
            'fields': ('created_by', 'created_at', 'updated_at', 'completed_at'),
        }),
    )
    readonly_fields = ('created_at', 'updated_at', 'completed_at', 'created_by')
    
    autocomplete_fields = ['assigned_to_user', 'assigned_to_group', 'task_type', 'status', 'payment_cash_register_for_supply']


    def assigned_to_user_display(self, obj):
        return obj.assigned_to_user.get_full_name() or obj.assigned_to_user.username if obj.assigned_to_user else "-"
    assigned_to_user_display.short_description = "Исполнитель (пользователь)"
    assigned_to_user_display.admin_order_field = 'assigned_to_user'

    def assigned_to_group_display(self, obj):
        return obj.assigned_to_group.name if obj.assigned_to_group else "-"
    assigned_to_group_display.short_description = "Исполнитель (группа)"
    assigned_to_group_display.admin_order_field = 'assigned_to_group'

    def related_object_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html

        if obj.related_object:
            try:
                admin_url = reverse(
                    f'admin:{obj.content_type.app_label}_{obj.content_type.model}_change',
                    args=[obj.object_id]
                )
                return format_html('<a href="{}">{}</a>', admin_url, str(obj.related_object))
            except Exception:
                return str(obj.related_object) 
        return "-"
    related_object_link.short_description = "Связанный объект"
    # related_object_link.allow_tags = True # allow_tags устарело, format_html само заботится о безопасности

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        user_groups = request.user.groups.all()
        from django.db.models import Q
        
        assigned_to_me = Q(assigned_to_user=request.user)
        assigned_to_my_groups = Q(assigned_to_group__in=user_groups)
        visible_by_type_for_my_groups = Q(task_type__default_visibility_groups__in=user_groups)
        
        qs = qs.filter(
            assigned_to_me | assigned_to_my_groups | visible_by_type_for_my_groups
        ).distinct()
        
        return qs

    def save_model(self, request, obj, form, change):
        if not obj.pk: 
            obj.created_by = request.user
        
        obj._performing_user = request.user 
        super().save_model(request, obj, form, change)

    # --- МЕТОД get_fieldsets ЗАКОММЕНТИРОВАН ДЛЯ ТЕСТА ---
    # def get_fieldsets(self, request, obj=None):
    #     fieldsets = super().get_fieldsets(request, obj)
    #     current_fieldsets = [list(fs) for fs in fieldsets]

    #     is_supply_payment_task = False
    #     if obj and obj.task_type:
    #         try:
    #             # Убедись, что TaskType импортирован, если будешь раскомментировать
    #             # from .models import TaskType 
    #             if obj.task_type.name == "Оформить оплату поставки": 
    #                 is_supply_payment_task = True
    #         except TaskType.DoesNotExist: # Обработка случая, если тип не найден
    #             pass
        
    #     final_fieldsets = []
    #     for name, options in current_fieldsets:
    #         if name == 'Параметры для "Оплаты поставки"': 
    #             if is_supply_payment_task:
    #                 final_fieldsets.append((name, options))
    #         else:
    #             final_fieldsets.append((name, options))
        
    #     return tuple(final_fieldsets)