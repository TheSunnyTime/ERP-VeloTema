# ERP/suppliers/views.py
from django.shortcuts import render, redirect, get_object_or_404
# from django.http import HttpResponse # HttpResponse используется для скачивания CSV в export_stock_levels_view
from django.urls import reverse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db import transaction
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP 
import csv

from .forms import SupplyItemCSVImportForm
from .models import Supply, SupplyItem # Убедись, что SupplyItem импортирован
from products.models import Product

@staff_member_required
def import_supply_items_from_csv_view(request):
    form = SupplyItemCSVImportForm(request.POST or None, request.FILES or None)
    
    if request.method == 'POST':
        if form.is_valid():
            supply_instance = form.cleaned_data['supply_to_update']
            csv_file = form.cleaned_data['csv_file']

            if supply_instance.status != Supply.STATUS_DRAFT:
                messages.error(request, f"Импорт позиций возможен только для поставок в статусе 'Черновик'. "
                                        f"Поставка №{supply_instance.id} имеет статус '{supply_instance.get_status_display()}'.")
                return redirect(reverse('suppliers:import_supply_items_csv'))

            created_count = 0
            skipped_rows_details = []
            
            try:
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.reader(decoded_file, delimiter=';')
                
                header = next(reader, None) 
                if header:
                    print(f"[CSV SupplyItem Import] CSV Header: {header}")

                with transaction.atomic():
                    for i, row in enumerate(reader, start=2): 
                        if not any(field.strip() for field in row):
                            continue
                        
                        # Ожидаем 4 колонки: ID, Наименование, Количество, Себестоимость
                        if len(row) < 4:
                            skipped_rows_details.append(f"Строка {i}: Недостаточно данных (ожидается 4 колонки). Содержимое: {row}")
                            continue

                        product_id_str = row[0].strip()
                        product_name_csv = row[1].strip() # Используем для информации/логов
                        quantity_str = row[2].strip()
                        cost_str = row[3].strip().replace(',', '.')

                        if not product_id_str or not quantity_str or not cost_str:
                            skipped_rows_details.append(
                                f"Строка {i} (Товар из CSV: '{product_name_csv}'): Одно из ключевых полей (ID, Кол-во, Себест.) пустое. "
                                f"ID: '{product_id_str}', Кол-во: '{quantity_str}', Себест: '{cost_str}'."
                            )
                            continue
                        
                        product_obj = None
                        try:
                            product_id = int(product_id_str)
                            product_obj = Product.objects.get(pk=product_id)
                        except (ValueError, Product.DoesNotExist):
                            skipped_rows_details.append(f"Строка {i} (Товар из CSV: '{product_name_csv}'): Товар с ID '{product_id_str}' не найден.")
                            continue
                        
                        try:
                            quantity = int(quantity_str)
                            if quantity < 0: # Позволим 0, если нужно обнулить, но для прихода обычно > 0
                                raise ValueError("Количество не может быть отрицательным.")
                        except ValueError as e_qty:
                            skipped_rows_details.append(f"Строка {i} (Товар: {product_obj.name}): Неверное количество '{quantity_str}'. ({e_qty})")
                            continue

                        try:
                            cost_per_unit = Decimal(cost_str)
                            if cost_per_unit < Decimal('0.00'):
                                 raise ValueError("Себестоимость не может быть отрицательной.")
                        except InvalidOperation as e_cost:
                            skipped_rows_details.append(f"Строка {i} (Товар: {product_obj.name}): Неверная себестоимость '{cost_str}'. ({e_cost})")
                            continue
                        except ValueError as e_cost_val:
                            skipped_rows_details.append(f"Строка {i} (Товар: {product_obj.name}): {e_cost_val}")
                            continue
                        
                        # Если количество 0, возможно, мы не хотим создавать позицию
                        if quantity == 0:
                            skipped_rows_details.append(f"Строка {i} (Товар: {product_obj.name}): Количество 0, позиция пропущена.")
                            continue

                        # Создаем SupplyItem (get_or_create здесь не нужен, т.к. для технической поставки мы обычно создаем новые записи)
                        # Если нужно обновлять существующие в той же поставке, логика усложнится.
                        # Для ввода начальных остатков обычно создают одну чистую техническую поставку.
                        if SupplyItem.objects.filter(supply=supply_instance, product=product_obj).exists():
                            skipped_rows_details.append(f"Строка {i}: Товар '{product_obj.name}' уже существует в этой поставке. Позиция пропущена во избежание дублирования.")
                            continue

                        supply_item_obj = SupplyItem.objects.create(
                            supply=supply_instance,
                            product=product_obj,
                            quantity_received=quantity,
                            cost_price_per_unit=cost_per_unit.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                            # quantity_remaining_in_batch будет установлен в SupplyItem.save()
                        )
                        created_count += 1
                        print(f"[CSV SupplyItem Import] Создана позиция: {supply_item_obj}")
                
                if created_count > 0:
                    messages.success(request, f"Успешно импортировано {created_count} новых позиций в поставку №{supply_instance.id}.")
                
                if not skipped_rows_details and created_count == 0 and header:
                    messages.info(request, "Файл обработан, но не найдено подходящих позиций для импорта (возможно, все уже существуют или файл пуст после заголовка).")
                
                for skipped_msg in skipped_rows_details:
                    messages.warning(request, skipped_msg)
                
                if not created_count and skipped_rows_details:
                     messages.error(request, "Во время импорта не удалось обработать некоторые строки. Позиции не были добавлены.")

                return redirect(reverse('admin:suppliers_supply_change', args=[supply_instance.id]))

            except UnicodeDecodeError:
                messages.error(request, "Не удалось декодировать файл. Убедитесь, что файл в кодировке UTF-8.")
            except csv.Error as e_csv:
                messages.error(request, f"Ошибка чтения CSV файла: {e_csv}")
            except Exception as e_global:
                messages.error(request, f"Произошла непредвиденная ошибка при обработке файла: {str(e_global)}")
                import traceback
                traceback.print_exc()
        else:
            messages.error(request, "Пожалуйста, исправьте ошибки в форме.")

    context = {
        'title': 'Импорт позиций поставки из CSV',
        'form': form,
        'opts': Supply._meta if 'Supply' in locals() else None, # Безопасный доступ к _meta
        'app_label': Supply._meta.app_label if 'Supply' in locals() and hasattr(Supply._meta, 'app_label') else 'suppliers',
        'has_permission': request.user.is_staff,
    }
    return render(request, 'suppliers/import_supply_items_form.html', context)