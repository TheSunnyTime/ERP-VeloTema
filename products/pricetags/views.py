# products/pricetags/views.py (ОБНОВЛЁН)
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse # <--- ДОБАВЬ JsonResponse СЮДА
from django.views.decorators.csrf import csrf_exempt # Пока оставим для удобства тестирования POST
from django.template.loader import render_to_string # Для рендеринга HTML-шаблонов
import json
from datetime import datetime # Для даты и времени печати
from ..models import Product # Импортируем модель Product из родительского модуля products
from weasyprint import HTML, CSS # Импортируем WeasyPrint
from .forms import PricetagProductSearchForm # <--- ДОБАВЬ ИЛИ УБЕДИСЬ, ЧТО ЭТА СТРОКА ЕСТЬ
from django.contrib import admin # <--- ДОБАВЬ ИЛИ УБЕДИСЬ, ЧТО ЭТА СТРОКА ЕСТЬ
from ..models import Product # <--- убедитесь, что Product импортирован

# --- Представление для выбора товаров (без изменений) ---
def select_products_for_pricetags(request):
    """
    Представление для выбора товаров для печати ценников.
    """
    form = PricetagProductSearchForm()
    context = {
        'form': form,
        'site_header': admin.site.site_header, # <--- ПЕРЕДАЕМ СЮДА
        'site_title': admin.site.site_title,   # <--- И ЭТО ТОЖЕ
    }
    context = {
        'form': form, # Передаем форму в контекст
        'site_header': admin.site.site_header,
        'site_title': admin.site.site_title,
    }
    return render(request, 'pricetags/test.html', context)


# --- Представление для генерации PDF (ОБНОВЛЕНО) ---
@csrf_exempt # Временное решение для тестирования, потом нужен будет нормальный CSRF
def generate_pricetags_pdf(request):
    """
    Представление для генерации PDF с ценниками.
    """
    if request.method == 'POST':
        try:
            product_ids_str = request.POST.get('product_ids')
            if not product_ids_str:
                return HttpResponse("Не выбраны товары для печати.", status=400)

            product_ids = json.loads(product_ids_str)
            
            # Получаем выбранные товары из базы данных
            # Используем .in_bulk() для получения объектов по ID, это эффективно
            # products_map = Product.objects.in_bulk(product_ids)
            # products_map возвращает словарь {id: obj}, поэтому для сохранения порядка
            # или для гарантии наличия, лучше получить через filter и отсортировать
            selected_products = Product.objects.filter(id__in=product_ids).order_by('name') # Сортируем по имени

            if not selected_products.exists(): # Проверяем, есть ли вообще товары
                return HttpResponse("Выбранные товары не найдены.", status=404)

            # Формируем HTML-контент для всех ценников
            # Мы хотим, чтобы 18 ценников были на одной странице А4.
            # Для этого рендерим один и тот же шаблон много раз и передаем в него продукт.
            # Общий шаблон pricetag_template.html уже содержит структуру для A4 и flexbox.
            
            context = {
                'products': selected_products,
                'current_datetime': datetime.now() # Текущая дата и время
            }
            
            # Рендерим весь HTML-документ, который WeasyPrint будет конвертировать
            html_string = render_to_string('pricetags/test2.html', context)
            
            # Создаем HTML объект из строки
            html = HTML(string=html_string)
            
            # Генерируем PDF
            # Можно добавить CSS для стилизации, если он внешний, но пока все в HTML <style>
            pdf_file = html.write_pdf()

            # Отдаем PDF пользователю
            response = HttpResponse(pdf_file, content_type='application/pdf')
            response['Content-Disposition'] = 'inline; filename="pricetags.pdf"' # inline для предпросмотра в браузере
            # Если нужно сразу скачать, поменяй на 'attachment; filename="pricetags.pdf"'
            return response

        except json.JSONDecodeError:
            return HttpResponse("Некорректный формат данных product_ids.", status=400)
        except Exception as e:
            # В реальной системе нужно логировать эту ошибку
            print(f"Ошибка при генерации ценников: {e}")
            return HttpResponse(f"Произошла ошибка при генерации ценников: {e}", status=500)
    
    return HttpResponse("Метод не разрешен.", status=405)
def get_product_data_api_view(request, product_id):
    """
    API View для получения полных данных о товаре по его ID.
    """
    try:
        product = Product.objects.get(pk=product_id)
        data = {
            'id': product.pk,
            'name': product.name,
            'sku': product.sku if product.sku else '',
            'retail_price': str(product.retail_price), # Десятичные числа как строки
            'available_stock_quantity': product.get_available_stock_quantity,
        }
        return JsonResponse(data)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Товар не найден'}, status=404)
    except Exception as e:
        print(f"Ошибка при получении данных товара {product_id}: {e}")
        return JsonResponse({'error': f'Ошибка сервера: {e}'}, status=500)