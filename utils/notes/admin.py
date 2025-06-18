# F:\CRM 2.0\ERP\utils\notes\admin.py

from django.contrib import admin
from .models import ServiceNote

@admin.register(ServiceNote)
class ServiceNoteAdmin(admin.ModelAdmin):
    """
    Админка для служебных заметок
    Здесь админы могут создавать и редактировать заметки о функциях системы
    """
    
    # Какие колонки показать в списке заметок
    list_display = (
        'title',           # Заголовок заметки
        'category',        # Категория (Экспорт, Импорт и т.д.)
        'is_important',    # Важная заметка или нет
        'is_admin_only',   # НОВОЕ: Только для администрации
        'created_by',      # Кто создал
        'created_at'       # Когда создана
    )
    # Фильтры в правой части экрана
    list_filter = (
        'category',        # Фильтр по категории
        'is_important',    # Фильтр по важности
        'is_admin_only',   # НОВОЕ: Фильтр "Только для админов"
        'created_at'       # Фильтр по дате создания
    )
    
    # Поиск по этим полям
    search_fields = ('title', 'content')
    
    # Поля только для чтения (нельзя изменить)
    readonly_fields = ('created_by', 'created_at', 'updated_at')
    
    # Группировка полей на странице редактирования
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'content', 'category', 'is_important', 'is_admin_only')
        }),
        ('Служебная информация', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)  # Эта группа будет свёрнута
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """
        Когда сохраняем заметку - автоматически записываем,
        кто её создал (если это новая заметка)
        """
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

        # ДОБАВЬ ЭТУ НОВУЮ ФУНКЦИЮ:
    def get_queryset(self, request):
        """
        Показываем заметки в зависимости от прав пользователя
        Если пользователь НЕ админ - скрываем секретные заметки
        """
        qs = super().get_queryset(request)
        
        # Проверяем: суперпользователь или в группе "Администраторы"
        is_admin = (
            request.user.is_superuser or 
            request.user.groups.filter(name='Администраторы').exists()
        )
        
        # Если НЕ админ - показываем только обычные заметки
        if not is_admin:
            qs = qs.filter(is_admin_only=False)
        
        return qs