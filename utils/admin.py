# F:\CRM 2.0\ERP\utils\admin.py
from django.contrib import admin, messages
from django.urls import path, reverse 
from django.http import HttpResponseRedirect
from django.core.exceptions import PermissionDenied # Не используется напрямую в этом файле, но может быть полезно
from django.utils.html import format_html
from .notes.admin import ServiceNoteAdmin

# Модели из .models текущего приложения (utils)
from .models import (
    ProductPriceImporter, 
    DocumentType, 
    DocumentTemplate, 
    ExportStockLevelsTool,
    ImportSupplyItemsTool # Наша новая модель для ссылки
)
# View из .views текущего приложения (utils)
from .views import product_csv_import_view, export_stock_levels_view # Импортируем обе view

@admin.register(ProductPriceImporter)
class ProductPriceImporterAdmin(admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        # Убедись, что право 'utils.can_import_product_prices' определено в Meta ProductPriceImporter, если используется
        if not request.user.has_perm('utils.can_import_product_prices') and not request.user.is_superuser:
            messages.error(request, "У тебя нет прав для импорта прайс-листов.")
            return HttpResponseRedirect(reverse('admin:index'))
        try:
            import_url = reverse('utils:import_product_csv') # Предполагаем, что такой URL есть в utils.urls
        except Exception as e:
            messages.error(request, f"Ошибка: URL 'utils:import_product_csv' для импорта прайс-листа не настроен ({e}).")
            return HttpResponseRedirect(reverse('admin:index'))
        return HttpResponseRedirect(import_url)

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    
    def has_module_permission(self, request):
        if request.user.is_superuser: return True
        return request.user.has_perm('utils.can_import_product_prices')

@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'related_model_content_type_name', 'display_placeholders_hint_summary')
    search_fields = ('name',)
    list_filter = ('related_model',)
    ordering = ['name']
    fields = ('name', 'related_model', 'placeholders_hint')

    def related_model_content_type_name(self, obj):
        if obj.related_model:
            return f"{obj.related_model.app_label.capitalize()} - {obj.related_model.name.capitalize()}"
        return "-"
    related_model_content_type_name.short_description = "Связанная модель"
    related_model_content_type_name.admin_order_field = 'related_model'

    def display_placeholders_hint_summary(self, obj):
        if obj.placeholders_hint:
            return (obj.placeholders_hint[:75] + '...') if len(obj.placeholders_hint) > 75 else obj.placeholders_hint
        return "-"
    display_placeholders_hint_summary.short_description = "Подсказка по плейсхолдерам (начало)"
    
    def has_module_permission(self, request):
        return request.user.has_perm('utils.view_documenttype') or \
               request.user.has_perm('utils.add_documenttype') or \
               request.user.has_perm('utils.change_documenttype') or \
               request.user.has_perm('utils.delete_documenttype') or \
               request.user.is_superuser

@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'document_type', 'is_active', 'updated_at')
    list_filter = ('document_type', 'is_active', 'allowed_editing_groups')
    search_fields = ('name', 'document_type__name')
    filter_horizontal = ('allowed_editing_groups',)
    ordering = ['document_type', 'name']
    
    fields = ('name', 'document_type', 'template_content', 'is_active', 'allowed_editing_groups', 
              'display_placeholders_hint_on_form', 'created_at', 'updated_at')
    readonly_fields = ('display_placeholders_hint_on_form', 'created_at', 'updated_at')

    def display_placeholders_hint_on_form(self, obj=None):
        doc_type = None
        if obj and obj.document_type:
            doc_type = obj.document_type
        
        if doc_type and doc_type.placeholders_hint:
            content = format_html("<p style='margin-top:0;'><strong>Подсказка по плейсхолдерам для типа '{}':</strong></p>", doc_type.name)
            content += format_html("<pre style='white-space: pre-wrap; background-color: var(--body-quiet-color, #f7f7f7); border: 1px solid var(--border-color, #ccc); padding: 10px; border-radius: 4px; color: var(--body-fg);'>{}</pre>", doc_type.placeholders_hint)
            return content
        elif doc_type:
            return "Для выбранного типа документа ('{}') подсказка по плейсхолдерам не заполнена.".format(doc_type.name)
        return "Выберите 'Тип документа', чтобы увидеть подсказку по плейсхолдерам (появится после сохранения или при редактировании)."
    display_placeholders_hint_on_form.short_description = "Доступные плейсхолдеры"

    def has_change_permission(self, request, obj=None):
        if not obj: 
            return request.user.has_perm('utils.add_documenttemplate') or request.user.is_superuser
        if request.user.is_superuser:
            return True
        if obj.allowed_editing_groups.exists():
            user_in_allowed_group = obj.allowed_editing_groups.filter(pk__in=request.user.groups.all()).exists()
            return user_in_allowed_group and request.user.has_perm('utils.change_documenttemplate')
        return request.user.has_perm('utils.change_documenttemplate')

    def has_module_permission(self, request):
        return request.user.has_perm('utils.view_documenttemplate') or \
               request.user.has_perm('utils.add_documenttemplate') or \
               request.user.has_perm('utils.change_documenttemplate') or \
               request.user.has_perm('utils.delete_documenttemplate') or \
               request.user.is_superuser

@admin.register(ExportStockLevelsTool)
class ExportStockLevelsToolAdmin(admin.ModelAdmin):
    def get_urls(self):
        urls = [] 
        custom_urls = [
            path('', self.admin_site.admin_view(export_stock_levels_view), name='utils_exportstocklevelstool_changelist'),
        ]
        return custom_urls + urls # Объединяем, хотя urls пуст

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    def has_module_permission(self, request):
        if request.user.is_staff: return True # Доступ для всех сотрудников
        return False

# --- ИСПРАВЛЕННЫЙ АДМИН-КЛАСС ДЛЯ ИНСТРУМЕНТА ИМПОРТА ПОЗИЦИЙ ПОСТАВКИ ---
@admin.register(ImportSupplyItemsTool) # <--- РАСКОММЕНТИРОВАЛ ДЕКОРАТОР
class ImportSupplyItemsToolAdmin(admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        # Перенаправляем пользователя на страницу импорта CSV для позиций поставки
        try:
            # Убедись, что в suppliers/urls.py есть app_name = 'suppliers'
            # и путь с name='import_supply_items_csv'
            import_url = reverse('suppliers:import_supply_items_csv')
            return HttpResponseRedirect(import_url)
        except Exception as e:
            self.message_user(request, f"Ошибка: URL для импорта позиций поставки ('suppliers:import_supply_items_csv') не настроен или не найден ({e}). Проверьте urls.py приложений suppliers и utils.", level=messages.ERROR)
            # Редирект на список моделей приложения utils, если что-то пошло не так с URL импорта
            return HttpResponseRedirect(reverse('admin:app_list', kwargs={'app_label': 'utils'}))

    # Запрещаем стандартные действия
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

    # Контролируем, кто видит этот пункт меню в разделе "Утилиты"
    def has_module_permission(self, request):
        # Разрешаем, например, только staff users или тем, у кого есть специфическое право
        if request.user.is_staff: 
            return True
        return False