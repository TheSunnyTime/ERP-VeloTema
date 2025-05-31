# F:\CRM 2.0\ERP\utils\admin.py
from django.contrib import admin
from django.urls import reverse # Убрал 'path', так как он здесь не используется напрямую
from django.http import HttpResponseRedirect
from django.core.exceptions import PermissionDenied
from django.utils.html import format_html
from django.contrib.auth.models import Group # Используется в DocumentTemplateAdmin
from django.contrib import messages # Используется в ProductPriceImporterAdmin

# Модели из .models текущего приложения (utils)
from .models import (
    ProductPriceImporter, DocumentType, DocumentTemplate
    # УБРАНЫ: EmployeeRate, SalaryCalculation, SalaryPayment, SalaryCalculationDetail
    # Это правильно, так как они теперь в salary_management/admin.py
)
# View из .views текущего приложения (utils)
from .views import product_csv_import_view 

@admin.register(ProductPriceImporter)
class ProductPriceImporterAdmin(admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        if not request.user.has_perm('utils.can_import_product_prices'):
            messages.error(request, "У тебя нет прав для импорта прайс-листов.")
            return HttpResponseRedirect(reverse('admin:index'))
            
        import_url = reverse('utils:import_product_csv')
        return HttpResponseRedirect(import_url)

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    
    def has_view_permission(self, request, obj=None): # Право на "просмотр" самой прокси-модели (ссылки)
        return request.user.has_perm('utils.can_import_product_prices') or request.user.is_superuser

    def has_module_permission(self, request): # Определяет, будет ли модель видна в списке моделей приложения
        # Для прокси-модели, которая является ссылкой на действие, логично,
        # чтобы она была видна, если пользователь имеет право на это действие.
        return request.user.has_perm('utils.can_import_product_prices') or request.user.is_superuser

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
        # Стандартный и рекомендуемый подход для большинства моделей:
        # Модель видна в приложении, если у пользователя есть хотя бы одно из стандартных CRUD прав.
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
        
        # Твой предыдущий закомментированный код для _current_document_type_for_hint я убрал,
        # так как он не был полностью реализован и мог вызывать вопросы.
        # Подсказка будет корректно отображаться при редактировании существующего шаблона.
        # Для новых шаблонов она появится после первого сохранения с выбранным типом документа.

        if doc_type and doc_type.placeholders_hint:
            content = format_html("<p style='margin-top:0;'><strong>Подсказка по плейсхолдерам для типа '{}':</strong></p>", doc_type.name)
            content += format_html("<pre style='white-space: pre-wrap; background-color: var(--body-quiet-color, #f7f7f7); border: 1px solid var(--border-color, #ccc); padding: 10px; border-radius: 4px; color: var(--body-fg);'>{}</pre>", doc_type.placeholders_hint)
            return content
        elif doc_type:
             return "Для выбранного типа документа ('{}') подсказка по плейсхолдерам не заполнена.".format(doc_type.name)
        return "Выберите 'Тип документа', чтобы увидеть подсказку по плейсхолдерам (подсказка появится после сохранения или при редактировании существующего шаблона)."
    display_placeholders_hint_on_form.short_description = "Доступные плейсхолдеры"

    def has_change_permission(self, request, obj=None):
        if not obj: 
            # Разрешаем доступ к форме добавления, если есть право на добавление
            return request.user.has_perm('utils.add_documenttemplate') or request.user.is_superuser
        if request.user.is_superuser:
            return True
        # Если группы заданы, проверяем членство пользователя в них И общее право на изменение
        if obj.allowed_editing_groups.exists():
            user_in_allowed_group = obj.allowed_editing_groups.filter(pk__in=request.user.groups.all()).exists()
            return user_in_allowed_group and request.user.has_perm('utils.change_documenttemplate')
        # Если группы не заданы, то право на изменение определяется общим пермишеном 'utils.change_documenttemplate'
        return request.user.has_perm('utils.change_documenttemplate')

    def has_module_permission(self, request):
        # Аналогично DocumentTypeAdmin
        return request.user.has_perm('utils.view_documenttemplate') or \
               request.user.has_perm('utils.add_documenttemplate') or \
               request.user.has_perm('utils.change_documenttemplate') or \
               request.user.has_perm('utils.delete_documenttemplate') or \
               request.user.is_superuser

# --- Админ-классы для моделей Зарплаты здесь больше НЕ НУЖНЫ ---
# Они должны быть в salary_management/admin.py