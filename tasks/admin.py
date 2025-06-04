# tasks/admin.py
from django import forms
from django.contrib import admin
from .models import TaskStatus, TaskType, Task
from django.utils.html import format_html
from uiconfig.models import TaskStatusColor # Убедись, что этот импорт корректен


class TaskAdminForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = '__all__'

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
    filter_horizontal = ('default_visibility_groups',)

    def get_default_visibility_groups(self, obj):
        return ", ".join([g.name for g in obj.default_visibility_groups.all()])
    get_default_visibility_groups.short_description = "Группы с авто-видимостью"


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    form = TaskAdminForm # Если используешь

    # --- РАСКОММЕНТИРУЙ __init__ ---
    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        try:
            self.task_status_colors_map = {
                color.task_status.name: color.hex_color 
                for color in TaskStatusColor.objects.select_related('task_status').all()
            }
        except Exception as e:
            print(f"Warning (TaskAdmin): Could not load task status colors: {e}")
            self.task_status_colors_map = {}

    # --- РАСКОММЕНТИРУЙ colored_status_display ---
    def colored_status_display(self, obj: Task):
        if not obj.status: 
            return "-"
        status_name = obj.status.name 
        status_display_text = obj.status.name 
        hex_color = self.task_status_colors_map.get(status_name)
        if hex_color:
            try:
                r = int(hex_color[1:3], 16)
                g = int(hex_color[3:5], 16)
                b = int(hex_color[5:7], 16)
                text_color = '#ffffff' if (r * 0.299 + g * 0.587 + b * 0.114) < 128 else '#000000'
                return format_html(
                    '<span style="background-color: {0}; padding: 3px 7px; border-radius: 4px; color: {1};"><strong>{2}</strong></span>',
                    hex_color, text_color, status_display_text)
            except ValueError: 
                return status_display_text
        return status_display_text
    colored_status_display.short_description = 'Статус' 
    colored_status_display.admin_order_field = 'status__name' 

    list_display = (
        'title', 
        'task_type', 
        'colored_status_display',
        'priority', 
        'assigned_to_user_display', 
        'assigned_to_group_display',
        'due_date', 
        'created_at',
        'related_object_link' 
    )
    list_filter = (
        'status', # Здесь фильтр все еще по обычному статусу, это нормально
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
    
    # Убираем 'status' из list_editable, так как цветной статус там отобразить стандартно нельзя.
    # Редактирование статуса будет происходить на странице самой задачи.
    list_editable = ('priority',) 

    fieldsets = (
        (None, {
            'fields': ('title', 'description')
        }),
        ('Детали задачи', {
            'fields': ('task_type', 'status', 'priority', 'due_date') # Статус здесь будет обычным select
        }),
        ('Назначение', {
            'fields': ('assigned_to_user', 'assigned_to_group')
        }),
        ('Связанный объект (Опционально)', {
            'classes': ('collapse',), 
            'fields': ('content_type', 'object_id')
        }),
        ('Параметры для "Оплаты поставки"', { 
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
        from django.urls import reverse # Импорт внутри метода, чтобы избежать циклических зависимостей при запуске

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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        user_groups = request.user.groups.all()
        from django.db.models import Q # Импорт внутри метода
        
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

    # --- МЕТОД get_fieldsets ОСТАЕТСЯ ЗАКОММЕНТИРОВАННЫМ ---
    # def get_fieldsets(self, request, obj=None):
    #    ...