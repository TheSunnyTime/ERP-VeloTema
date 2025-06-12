from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from .models import Shift, ColorRule, ColorAssignment, ScheduleTemplate
from .admin_views import calendar_view
from django.contrib.auth.models import User
from django.contrib import messages
from datetime import timedelta, date

# --- ScheduleTemplateAdmin и экшены без изменений ---

@admin.register(ScheduleTemplate)
class ScheduleTemplateAdmin(admin.ModelAdmin):
    list_display = ('employee', 'work_days', 'start_time', 'end_time')
    search_fields = ('employee__username', 'employee__first_name', 'employee__last_name')
    verbose_name = "Шаблон расписания"
    verbose_name_plural = "Шаблоны расписаний"

def apply_schedule_template(modeladmin, request, queryset):
    from datetime import date, timedelta

    for employee in queryset:
        try:
            template = ScheduleTemplate.objects.get(employee=employee)
        except ScheduleTemplate.DoesNotExist:
            messages.warning(request, f"Нет шаблона у {employee}")
            continue

        today = date.today()
        first_day = today.replace(day=1)
        next_month = (first_day + timedelta(days=32)).replace(day=1)
        last_day = next_month - timedelta(days=1)

        deleted_count, _ = Shift.objects.filter(
            employee=employee,
            date__gte=first_day,
            date__lte=last_day
        ).delete()

        current_day = first_day
        work_days = template.get_work_days_list()
        created_count = 0

        while current_day <= last_day:
            if current_day.weekday() in work_days:
                Shift.objects.create(
                    employee=employee,
                    date=current_day,
                    start_time=template.start_time,
                    end_time=template.end_time,
                )
                created_count += 1
            current_day += timedelta(days=1)
        messages.success(
            request,
            f"Для {employee} удалено смен: {deleted_count}, создано новых: {created_count}"
        )

apply_schedule_template.short_description = "Перезаписать смены на месяц по шаблону"

class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'first_name', 'last_name', 'is_active')
    search_fields = ('username', 'first_name', 'last_name')
    actions = [apply_schedule_template]

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# --- ShiftAdmin с ссылкой на календарь в changelist ---
@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ('employee_name', 'date', 'start_time', 'end_time', 'duration_display', 'notes_preview', 'updated_at')
    list_filter = ('date', 'employee')
    search_fields = ('employee__username', 'employee__first_name', 'employee__last_name', 'notes')
    autocomplete_fields = ['employee']
    list_select_related = ['employee']

    fieldsets = (
        (None, {
            'fields': ('employee', 'date', ('start_time', 'end_time'))
        }),
        ('Дополнительно', {
            'fields': ('notes',)
        }),
        ('Информация о записи', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')

    def employee_name(self, obj):
        return obj.employee.get_full_name() or obj.employee.username
    employee_name.short_description = "Сотрудник"
    employee_name.admin_order_field = 'employee__last_name'

    def duration_display(self, obj):
        duration_hours = obj.duration
        if duration_hours > 0:
            return f"{duration_hours:.2f} ч."
        return "-"
    duration_display.short_description = "Длительность"

    def notes_preview(self, obj):
        if obj.notes:
            return (obj.notes[:75] + '...') if len(obj.notes) > 75 else obj.notes
        return "-"
    notes_preview.short_description = "Примечания"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "employee":
            kwargs["queryset"] = User.objects.filter(is_active=True).order_by('last_name', 'first_name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('calendar/', self.admin_site.admin_view(calendar_view), name='calendar'),
        ]
        return custom_urls + urls

    # Добавляем ссылку на календарь смен на страницу списка смен (вверху)
    def changelist_view(self, request, extra_context=None):
        calendar_url = reverse('admin:calendar')
        if extra_context is None:
            extra_context = {}
        extra_context['calendar_link'] = calendar_url
        return super().changelist_view(request, extra_context=extra_context)

# --- ColorRuleAdmin и ColorAssignmentAdmin без изменений ---
@admin.register(ColorRule)
class ColorRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'hex_color', 'colored_preview', 'description_preview')
    search_fields = ('name', 'hex_color', 'description')

    def colored_preview(self, obj):
        from django.utils.html import format_html
        if obj.hex_color:
            is_valid_hex = obj.hex_color.startswith('#') and len(obj.hex_color) in [4, 7]
            if is_valid_hex:
                try:
                    hex_val = obj.hex_color.lstrip('#')
                    rgb = tuple(int(hex_val[i:i+len(hex_val)//3], 16) for i in range(0, len(hex_val), len(hex_val)//3))
                    if len(hex_val) == 3:
                        rgb = tuple(c*17 for c in rgb)
                    brightness = (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000
                    text_color = '#000000' if brightness > 125 else '#FFFFFF'
                except ValueError:
                    text_color = '#000000'

                return format_html(
                    '<div style="background-color: {0}; color: {1}; padding: 5px; border-radius: 3px; text-align: center; width: 100px;">{0}</div>',
                    obj.hex_color,
                    text_color
                )
        return "N/A"
    colored_preview.short_description = "Предпросмотр"

    def description_preview(self, obj):
        if obj.description:
            return (obj.description[:75] + '...') if len(obj.description) > 75 else obj.description
        return "-"
    description_preview.short_description = "Описание"

@admin.register(ColorAssignment)
class ColorAssignmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'color_to_apply_display', 'priority', 'conditions_summary', 'is_active')
    list_filter = ('is_active', 'assigned_group', 'day_of_week', 'applies_to_workday')
    search_fields = ('name', 'color_to_apply__name', 'assigned_employee__username', 'assigned_group__name')
    autocomplete_fields = ['color_to_apply', 'assigned_employee', 'assigned_group']
    list_select_related = ['color_to_apply']

    fieldsets = (
        (None, {
            'fields': ('name', 'color_to_apply', 'priority', 'is_active')
        }),
        ('Условия применения (заполните нужные)', {
            'fields': ('assigned_employee', 'assigned_group', 'day_of_week', 'specific_date', 'applies_to_workday'),
            'description': "Если поле условия не заполнено, оно не учитывается. "
                           "Если указан 'Конкретный сотрудник', поле 'Группа сотрудников' игнорируется."
        }),
    )

    def color_to_apply_display(self, obj):
        from django.utils.html import format_html
        if obj.color_to_apply:
            rule = obj.color_to_apply
            hex_color = rule.hex_color
            text_color = '#000000'
            if hex_color:
                try:
                    hex_val = hex_color.lstrip('#')
                    rgb_tuple = tuple(int(hex_val[i:i+len(hex_val)//3], 16) for i in range(0, len(hex_val), len(hex_val)//3))
                    if len(hex_val) == 3: rgb_tuple = tuple(c*17 for c in rgb_tuple)
                    brightness = (rgb_tuple[0] * 299 + rgb_tuple[1] * 587 + rgb_tuple[2] * 114) / 1000
                    text_color = '#000000' if brightness > 125 else '#FFFFFF'
                except ValueError: pass

            return format_html(
                '<span style="background-color: {0}; color: {1}; padding: 2px 5px; border-radius: 3px;">{2}</span>',
                hex_color,
                text_color,
                rule.name
            )
        return "-"
    color_to_apply_display.short_description = "Применяемый цвет"
    color_to_apply_display.admin_order_field = 'color_to_apply__name'

    def conditions_summary(self, obj):
        conditions = []
        if obj.assigned_employee:
            conditions.append(f"Сотр: {obj.assigned_employee.get_full_name() or obj.assigned_employee.username}")
        elif obj.assigned_group:
            conditions.append(f"Группа: {obj.assigned_group.name}")

        if obj.day_of_week is not None:
            conditions.append(f"День нед: {obj.get_day_of_week_display()}")
        if obj.specific_date:
            conditions.append(f"Дата: {obj.specific_date.strftime('%d.%m.%Y')}")
        if obj.applies_to_workday is True:
            conditions.append("К рабочему дню")
        elif obj.applies_to_workday is False:
            conditions.append("К выходному дню")

        summary = ", ".join(conditions)
        return (summary[:100] + '...') if len(summary) > 100 else summary or "Нет доп. условий"
    conditions_summary.short_description = "Условия"