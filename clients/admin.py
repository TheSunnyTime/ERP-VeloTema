# CRM 2.0/ERP/clients/admin.py
from django.contrib import admin
from .models import ClientGroup, Client # Импортируем ваши модели

@admin.register(ClientGroup) # Регистрируем модель ClientGroup
class ClientGroupAdmin(admin.ModelAdmin):
    list_display = ('name',) # Показываем только название в списке групп
    search_fields = ('name',) # Позволяем искать по названию группы

@admin.register(Client) # Регистрируем модель Client
class ClientAdmin(admin.ModelAdmin):
    # В list_display можно оставить contact_person, если ты хочешь видеть его в общем списке клиентов,
    # но не на форме редактирования. Если не хочешь видеть и в списке, удали и отсюда.
    list_display = ('name', 'client_group', 'phone', 'email', 'contact_person', 'created_at') 
    list_filter = ('client_group', 'created_at') 
    # В search_fields можно оставить contact_person, если хочешь по нему искать,
    # даже если его нет на форме. Если не хочешь, удали.
    search_fields = ('name', 'phone', 'email', 'contact_person', 'notes') 
    autocomplete_fields = ('client_group',) 
    
    # --- ДОБАВЛЯЕМ ЭТОТ БЛОК ---
    # Явно указываем поля, которые должны отображаться на форме редактирования/добавления.
    # Поле 'contact_person' здесь НЕ указано, поэтому оно не будет отображаться на форме.
    fields = (
        'name', 
        'phone', 
        'email', 
        'address', 
        'client_group', 
        'notes',
        # 'created_at' # Это поле обычно делается readonly, см. ниже
    )
    # Поле 'created_at' обычно не редактируется вручную, делаем его readonly.
    # Если оно есть в 'fields', оно будет показано. Если нет, то нет.
    # Если хочешь видеть, но не редактировать:
    readonly_fields = ('created_at',) 
    # И тогда его нужно добавить в fields или fieldsets, если используешь fieldsets.
    # Если используешь fields и хочешь видеть created_at:
    # fields = ('name', 'phone', 'email', 'address', 'client_group', 'notes', 'created_at')
    # --- КОНЕЦ ДОБАВЛЕНИЯ ---

    class Media:
        js = (
            # УБИРАЕМ 'admin/js/jquery.init.js', # Django сам загрузит jQuery и создаст django.jQuery
            'vendor/inputmask/jquery.inputmask.js', # Путь к библиотеке Inputmask
            'clients/js/client_form_masks.js',      # Путь к твоему кастомному JS
        )