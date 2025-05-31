# F:\CRM 2.0\ERP\utils\views.py
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseServerError, JsonResponse
from django.urls import reverse
from django.contrib import admin, messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction, models # models импортирован для models.Sum
from django.contrib.contenttypes.models import ContentType
import re # Для регулярных выражений
from django.utils import timezone # Для timezone.now()
from django.contrib.auth import get_user_model
from django.db.models import Sum # Явный импорт Sum

# Импорты моделей из других приложений
from products.models import Product
from orders.models import Order, OrderType, OrderServiceItem, OrderProductItem # Добавил OrderProductItem
# from clients.models import Client # Client получаем через order.client

from .forms import CsvImportForm
from .models import ProductPriceImporter, DocumentType, DocumentTemplate # Модели, которые остаются в utils.models

# --- ИМПОРТ ЗАРПЛАТНЫХ МОДЕЛЕЙ ИЗ salary_management ---
from salary_management.models import SalaryCalculation, SalaryPayment
# EmployeeRate и SalaryCalculationDetail не используются напрямую в этих view из utils.views,
# но если бы использовались, импортировались бы также из salary_management.models

from django.utils.dateformat import DateFormat
from django.utils.formats import get_format # Для форматирования дат/времени
from datetime import date, timedelta # Для employee_salary_report_view

import csv
from decimal import Decimal, InvalidOperation # Убедись, что Decimal импортирован

User = get_user_model()

def product_csv_import_view(request):
    # ... (твой существующий код product_csv_import_view без изменений, как ты его прислал) ...
    # (Я его не повторяю для краткости)
    print("[CSV Import View] Entered view function.")
    if not request.user.has_perm('utils.can_import_product_prices') and not request.user.is_superuser:
        raise PermissionDenied("У тебя нет прав для импорта прайс-листов товаров.")
    form = CsvImportForm()
    if request.method == 'POST':
        form = CsvImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            if not csv_file.name.endswith('.csv'):
                messages.error(request, "Загруженный файл не является CSV файлом.")
            else:
                imported_count = 0; updated_count = 0; skipped_rows_details = []
                try:
                    decoded_file = csv_file.read().decode('utf-8').splitlines()
                    reader = csv.reader(decoded_file)
                    header = next(reader, None)
                    if not header or len(header) < 5:
                        messages.error(request, "Неверный формат или количество колонок в заголовке CSV файла.")
                    else:
                        with transaction.atomic():
                            for i, row in enumerate(reader, start=2):
                                try:
                                    if not any(field.strip() for field in row): continue
                                    if len(row) < 5: skipped_rows_details.append(f"Строка {i}: недостаточно данных."); continue
                                    csv_sku = row[0].strip(); csv_name = row[1].strip(); csv_quantity_str = row[2].strip()
                                    csv_wholesale_price_str = row[3].strip().replace(',', '.'); csv_retail_price_str = row[4].strip().replace(',', '.')
                                    if not csv_name:
                                        if csv_sku and not csv_quantity_str and not csv_wholesale_price_str: pass
                                        elif not csv_sku: pass
                                        else: skipped_rows_details.append(f"Строка {i}: Наименование пустое (Артикул/Категория: '{csv_sku}')."); continue
                                        continue
                                    if not csv_quantity_str and not csv_wholesale_price_str: continue
                                    quantity = 0
                                    try: quantity = int(csv_quantity_str) if csv_quantity_str else 0
                                    except ValueError: skipped_rows_details.append(f"Строка {i}, товар '{csv_name}': неверное Кол-во '{csv_quantity_str}'."); continue
                                    wholesale_price = Decimal('0.00')
                                    try:
                                        if not csv_wholesale_price_str: skipped_rows_details.append(f"Строка {i}, товар '{csv_name}': отсутствует Вход (ОПТ)."); continue
                                        wholesale_price = Decimal(csv_wholesale_price_str)
                                    except InvalidOperation: skipped_rows_details.append(f"Строка {i}, товар '{csv_name}': неверное значение ОПТ '{csv_wholesale_price_str}'."); continue
                                    retail_price = wholesale_price
                                    if csv_retail_price_str:
                                        try: retail_price = Decimal(csv_retail_price_str)
                                        except InvalidOperation: print(f"[CSV Import] Строка {i}, товар '{csv_name}': неверное РЦ '{csv_retail_price_str}', РЦ=ОПТ.")
                                    product_defaults = {'sku': csv_sku, 'stock_quantity': quantity, 'wholesale_price': wholesale_price, 'retail_price': retail_price}
                                    obj_product, created = Product.objects.update_or_create(name=csv_name, defaults=product_defaults)
                                    if created: imported_count += 1
                                    else: updated_count += 1
                                except Exception as e_row: skipped_rows_details.append(f"Строка {i} ({csv_name or csv_sku or 'Неизвестно'}): Внутренняя ошибка - {e_row}"); continue
                            if imported_count > 0: messages.success(request, f"Успешно импортировано {imported_count} новых товаров.")
                            if updated_count > 0: messages.success(request, f"Успешно обновлено {updated_count} существующих товаров.")
                            if not skipped_rows_details and not imported_count and not updated_count and (header is not None): messages.info(request, "Файл обработан, но не найдено товаров для импорта или обновления.")
                            for skipped_msg in skipped_rows_details: messages.warning(request, skipped_msg)
                            if not imported_count and not updated_count and skipped_rows_details: messages.error(request, "Во время импорта не удалось обработать некоторые строки. Товары не изменены.")
                            return HttpResponseRedirect(reverse('admin:products_product_changelist'))
                except UnicodeDecodeError: messages.error(request, "Не удалось декодировать файл. Пожалуйста, убедитесь, что файл сохранен в кодировке UTF-8.")
                except csv.Error as e_csv: messages.error(request, f"Ошибка чтения CSV файла: {e_csv}")
                except Exception as e_global: messages.error(request, f"Произошла непредвиденная ошибка при обработке файла: {e_global}")
    context = { **admin.site.each_context(request), 'title': 'Импорт прайс-листа товаров из CSV', 'form': form, 'app_label': 'utils', 'opts': ProductPriceImporter._meta }
    try: return render(request, 'admin/utils/product_csv_import_form.html', context)
    except Exception as e_render: import traceback; traceback.print_exc(); return HttpResponseServerError(f"Ошибка на сервере при отображении страницы импорта: {e_render}")
    return HttpResponseServerError("Непредвиденная ошибка: view завершилась без ответа.")


# --- ОБНОВЛЕННАЯ ФУНКЦИЯ generate_document_view ---
@login_required
def generate_document_view(request, template_id, object_id):
    doc_template = get_object_or_404(DocumentTemplate, pk=template_id, is_active=True)
    
    content_type_obj = doc_template.document_type.related_model
    model_class = None
    try:
        model_class = content_type_obj.model_class() 
        if model_class is None: 
            raise AttributeError(f"Не удалось определить класс модели для ContentType: {content_type_obj}")
        # Оптимизируем запрос, подтягивая связанные объекты сразу
        if model_class == Order:
            related_object = get_object_or_404(model_class.objects.select_related('client', 'employee', 'order_type'), pk=object_id)
        else:
            related_object = get_object_or_404(model_class, pk=object_id)
    except AttributeError as e:
        error_msg = f"Ошибка определения связанной модели для типа документа '{doc_template.document_type.name}': {e}"
        messages.error(request, error_msg)
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('admin:index')))
    except Exception as e: 
        error_msg = f"Ошибка получения объекта ID {object_id} для модели '{content_type_obj.model if content_type_obj else 'неизвестно'}': {e}"
        messages.error(request, error_msg)
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('admin:index')))

    placeholder_data = {}
    # Общие плейсхолдеры для любого объекта
    placeholder_data['object_id'] = str(related_object.pk)
    # Можно добавить #object_str# = str(related_object)

    # Данные Исполнителя (как в примере PDF "Заказ #1849 - HelloClient.pdf")
    placeholder_data['Исполнитель_Лого_Текст'] = "ВЕЛОТЕМА РЕМОНТ ВЕЛОСИПЕДОВ" # Для текстового лого
    placeholder_data['Исполнитель_Наименование_Полное'] = 'ООО "Рейвен Плюс"'
    placeholder_data['Исполнитель_УНП'] = "193760657"
    placeholder_data['Исполнитель_Адрес'] = "Г. Минск, Ул. Калиновского 68А, помещение 9"
    # placeholder_data['Исполнитель_Телефон'] = "ВАШ_ТЕЛЕФОН_ИСПОЛНИТЕЛЯ" # Если нужен
    # placeholder_data['QR_Код_Отзыв_URL'] = "URL_ДЛЯ_QR_КОДА" # Если нужен

    if isinstance(related_object, Order):
        order = related_object
        placeholder_data['Номер_Заказа'] = str(order.id)
        placeholder_data['Дата_Заказа'] = DateFormat(order.created_at).format(get_format('SHORT_DATE_FORMAT')) # дд.мм.гггг
        placeholder_data['Время_Заказа'] = DateFormat(order.created_at).format(get_format('TIME_FORMAT')) # чч:мм
        
        # Для "Дата и время составления акта" и "Дата выдачи" из примера PDF,
        # используем order.updated_at, предполагая, что это время последнего изменения заказа (например, выдачи)
        placeholder_data['Дата_Время_Акта'] = DateFormat(order.updated_at).format(get_format('DATETIME_FORMAT')) # дд.мм.гггг ЧЧ:ММ:СС
        placeholder_data['Дата_Акта_Короткая'] = DateFormat(order.updated_at).format(get_format('SHORT_DATE_FORMAT')) # дд.мм.гггг

        placeholder_data['Статус_Заказа'] = str(order.get_status_display())
        placeholder_data['Тип_Заказа'] = str(order.order_type.name) if order.order_type else "Не определен"
        placeholder_data['Общая_Сумма_Заказа'] = f"{order.calculate_total_amount():.2f}"
        placeholder_data['Заказ_Примечания'] = str(order.notes or "")
        
        # Описание велосипеда (извлекаем из примечаний, как в примере PDF)
        bike_desc_match = re.search(r"Велосипед:([^\n]+)", order.notes or "", re.IGNORECASE)
        placeholder_data['Велосипед_Описание'] = bike_desc_match.group(1).strip() if bike_desc_match else ""


        if order.client:
            placeholder_data['Клиент_Имя'] = str(order.client.name)
            placeholder_data['Клиент_Телефон'] = str(order.client.phone or "")
            placeholder_data['Клиент_Email'] = str(order.client.email or "")
            placeholder_data['Клиент_Адрес'] = str(order.client.address or "#Клиент_Адрес#") # Если пусто, оставляем как плейсхолдер
            placeholder_data['Клиент_КонтактноеЛицо'] = str(order.client.contact_person or "")
        
        if order.employee:
            employee_name_for_act = order.employee.first_name if order.employee.first_name else order.employee.username
            placeholder_data['Сотрудник_Имя_Акта'] = str(employee_name_for_act) # Для подписи "Менеджер: Имя"
            placeholder_data['Сотрудник_ФИО'] = str(order.employee.get_full_name() or order.employee.username)
            # placeholder_data['Сотрудник_Должность'] = "Менеджер" # Если должность фиксированная

    # Сначала заменяем все одиночные плейсхолдеры
    processed_content = doc_template.template_content
    for key, value in placeholder_data.items():
        # Оборачиваем ключ в #...# для замены
        processed_content = processed_content.replace(f"#{key}#", str(value))

    # Обработка списка позиций (товары и услуги вместе)
    if isinstance(related_object, Order):
        order = related_object
        # Используем общий блок #СписокПозиций_Начало# ... #СписокПозиций_Конец#
        items_block_match = re.search(r"#СписокПозиций_Начало#(.*?)#СписокПозиций_Конец#", processed_content, re.DOTALL | re.IGNORECASE)
        
        if items_block_match:
            item_template_str = items_block_match.group(1).strip() # Шаблон строки из документа
            rendered_all_items = []
            current_index = 0

            # Сначала товары
            for p_item in order.product_items.all().select_related('product'):
                current_index += 1
                row_content = item_template_str
                row_content = row_content.replace("#Поз_Номер#", str(current_index))
                row_content = row_content.replace("#Поз_Наименование#", str(p_item.product.name))
                row_content = row_content.replace("#Поз_Артикул#", str(p_item.product.sku or ""))
                row_content = row_content.replace("#Поз_Количество#", f"{p_item.quantity} шт.")
                item_price = p_item.price_at_order if p_item.price_at_order is not None else Decimal('0.00')
                item_total = p_item.get_item_total() if p_item.get_item_total() is not None else Decimal('0.00')
                row_content = row_content.replace("#Поз_Цена#", f"{item_price:.2f}")
                row_content = row_content.replace("#Поз_Сумма#", f"{item_total:.2f}")
                # Заглушки для гарантии и скидки (пока этих полей нет в моделях OrderProductItem/Product)
                row_content = row_content.replace("#Поз_Гарантия#", "14 дн.") 
                row_content = row_content.replace("#Поз_Скидка#", "0.00")
                rendered_all_items.append(row_content)

            # Затем услуги
            for s_item in order.service_items.all().select_related('service'):
                current_index += 1
                row_content = item_template_str
                row_content = row_content.replace("#Поз_Номер#", str(current_index))
                row_content = row_content.replace("#Поз_Наименование#", str(s_item.service.name))
                row_content = row_content.replace("#Поз_Артикул#", "") # У услуг нет артикула
                row_content = row_content.replace("#Поз_Количество#", str(s_item.quantity))
                item_price = s_item.price_at_order if s_item.price_at_order is not None else Decimal('0.00')
                item_total = s_item.get_item_total() if s_item.get_item_total() is not None else Decimal('0.00')
                row_content = row_content.replace("#Поз_Цена#", f"{item_price:.2f}")
                row_content = row_content.replace("#Поз_Сумма#", f"{item_total:.2f}")
                # Заглушки для гарантии и скидки (пока этих полей нет в моделях OrderServiceItem/Service)
                row_content = row_content.replace("#Поз_Гарантия#", "14 дн.") 
                row_content = row_content.replace("#Поз_Скидка#", "0.00")
                rendered_all_items.append(row_content)
            
            # Заменяем весь блок списка позиций на сгенерированные строки
            processed_content = processed_content.replace(items_block_match.group(0), "\n".join(rendered_all_items))
        else:
            print("[Generate Document View] Общий блок #СписокПозиций_Начало#...#СписокПозиций_Конец# не найден в HTML-шаблоне документа.")
            # Опционально: если общий блок не найден, можно попытаться обработать старые раздельные блоки
            # (но это усложнит код, лучше перейти на единый формат #СписокПозиций#)

    html_content_final = processed_content
    final_page_context = {
        **admin.site.each_context(request),
        'title': f"Документ: {doc_template.name} ({model_class._meta.verbose_name if model_class and hasattr(model_class, '_meta') else 'Объект'} №{related_object.id})",
        'document_title': doc_template.name,
        'document_content': html_content_final, 
        'app_label': 'utils', 
        'opts': DocumentTemplate._meta, 
    }
    return render(request, 'admin/utils/document_preview.html', final_page_context)

# --- Существующая функция employee_salary_report_view ---
@login_required
def employee_salary_report_view(request):
    # ... (твой существующий код employee_salary_report_view без изменений) ...
    # (Я его не повторяю для краткости)
    report_user = request.user; today = timezone.now().date()
    selected_year = None; selected_month = None
    try: selected_year = int(request.GET.get('year', ''))
    except (ValueError, TypeError): pass
    try: selected_month = int(request.GET.get('month', ''))
    except (ValueError, TypeError): pass
    is_redirect_needed = False
    if not selected_year or not selected_month or not (1 <= selected_month <= 12):
        first_day_of_current_month = today.replace(day=1); last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
        default_report_year = last_day_of_previous_month.year; default_report_month = last_day_of_previous_month.month
        if request.GET.get('year') is None and request.GET.get('month') is None: is_redirect_needed = True
        selected_year = selected_year if (selected_year and 1 <= (selected_month or 0) <= 12) else default_report_year
        selected_month = selected_month if (selected_month and 1 <= selected_month <= 12) else default_report_month
        if is_redirect_needed: return HttpResponseRedirect(reverse('utils:my_salary_report') + f'?year={selected_year}&month={selected_month}')
    start_of_selected_period = date(selected_year, selected_month, 1)
    accrued_before_period_data = SalaryCalculation.objects.filter(employee=report_user, period_date__lt=start_of_selected_period).aggregate(total=Sum('total_calculated_amount'))
    total_accrued_before_period = accrued_before_period_data['total'] or Decimal('0.00')
    paid_in_previous_years_data = SalaryPayment.objects.filter(employee=report_user, payment_for_year__lt=selected_year).aggregate(total=Sum('amount_paid'))
    total_paid_in_previous_years = paid_in_previous_years_data['total'] or Decimal('0.00')
    paid_in_current_year_before_month_data = SalaryPayment.objects.filter(employee=report_user, payment_for_year=selected_year, payment_for_month__lt=selected_month).aggregate(total=Sum('amount_paid'))
    total_paid_in_current_year_before_month = paid_in_current_year_before_month_data['total'] or Decimal('0.00')
    total_paid_before_period = total_paid_in_previous_years + total_paid_in_current_year_before_month
    opening_balance = total_accrued_before_period - total_paid_before_period
    salary_calculations = SalaryCalculation.objects.filter(employee=report_user, period_date__year=selected_year, period_date__month=selected_month).select_related('order').order_by('period_date', 'order__id')
    total_accrued_for_current_period_data = salary_calculations.aggregate(total=Sum('total_calculated_amount'))
    total_accrued_for_current_period = total_accrued_for_current_period_data['total'] or Decimal('0.00')
    salary_payments = SalaryPayment.objects.filter(employee=report_user, payment_for_year=selected_year, payment_for_month=selected_month).order_by('payment_date')
    total_paid_for_current_period_data = salary_payments.aggregate(total=Sum('amount_paid'))
    total_paid_for_current_period = total_paid_for_current_period_data['total'] or Decimal('0.00')
    closing_balance = opening_balance + total_accrued_for_current_period - total_paid_for_current_period
    current_period_start_nav = date(selected_year, selected_month, 1); prev_month_date = current_period_start_nav - timedelta(days=1)
    prev_month_url = reverse('utils:my_salary_report') + f'?year={prev_month_date.year}&month={prev_month_date.month}'
    next_month_date = (current_period_start_nav + timedelta(days=32)).replace(day=1); show_next_month = True
    if next_month_date.year > today.year or (next_month_date.year == today.year and next_month_date.month > today.month): show_next_month = False
    next_month_url = None
    if show_next_month: next_month_url = reverse('utils:my_salary_report') + f'?year={next_month_date.year}&month={next_month_date.month}'
    context = { **admin.site.each_context(request), 'title': f'Отчет по зарплате для {report_user.first_name or report_user.username} за {selected_month:02}.{selected_year}', 'report_user_display': report_user.first_name if report_user.first_name else report_user.username, 'selected_year': selected_year, 'selected_month': selected_month, 'opening_balance': opening_balance, 'salary_calculations': salary_calculations, 'total_accrued_for_current_period': total_accrued_for_current_period, 'salary_payments': salary_payments, 'total_paid_for_current_period': total_paid_for_current_period, 'closing_balance': closing_balance, 'has_permission': True, 'app_label': 'reports', 'prev_month_url': prev_month_url, 'next_month_url': next_month_url, 'is_current_month_selected': (selected_year == today.year and selected_month == today.month)}
    return render(request, 'admin/utils/employee_salary_report.html', context)

# --- Существующая API View-функция get_employee_balance_api ---
@login_required 
def get_employee_balance_api(request, employee_id):
    # ... (твой существующий код get_employee_balance_api без изменений) ...
    # (Я его не повторяю для краткости, но он должен остаться здесь)
    if not request.user.is_staff: return JsonResponse({'error': 'Доступ запрещен'}, status=403)
    try: employee = User.objects.get(pk=employee_id)
    except User.DoesNotExist: return JsonResponse({'error': 'Сотрудник не найден'}, status=404)
    total_accrued_data = SalaryCalculation.objects.filter(employee=employee).aggregate(total=Sum('total_calculated_amount'))
    total_accrued = total_accrued_data['total'] or Decimal('0.00')
    total_paid_data = SalaryPayment.objects.filter(employee=employee).aggregate(total=Sum('amount_paid'))
    total_paid = total_paid_data['total'] or Decimal('0.00')
    current_balance = total_accrued - total_paid
    data = {'employee_id': employee.id, 'employee_name': employee.first_name if employee.first_name else employee.username, 'current_balance': f"{current_balance:.2f}", 'total_accrued': f"{total_accrued:.2f}", 'total_paid': f"{total_paid:.2f}"}
    return JsonResponse(data)