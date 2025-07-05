# products/pricetags/views.py (ФИНАЛЬНО ИСПРАВЛЕННЫЙ И ОЧИЩЕННЫЙ)
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
import json
from datetime import datetime
from ..models import Product
from weasyprint import HTML, CSS
from django.contrib import admin

from .forms import PricetagProductSearchForm

def select_products_for_pricetags(request):
    """
    Представление для выбора товаров для печати ценников.
    """
    form = PricetagProductSearchForm()
    context = {
        'form': form,
        'site_header': admin.site.site_header,
        'site_title': admin.site.site_title,
    }
    # ИСПРАВЛЕНО: Правильный путь к шаблону для страницы выбора
    return render(request, 'pricetags/select_products_for_pricetags.html', context)


@csrf_exempt
def generate_pricetags_pdf(request):
    """
    Представление для генерации PDF с ценниками, учитывающее количество для каждого товара.
    """
    if request.method == 'POST':
        try:
            products_to_print_str = request.POST.get('products_to_print')
            if not products_to_print_str:
                return HttpResponse("Не выбраны товары для печати.", status=400)

            products_to_print_list = json.loads(products_to_print_str)
            
            product_ids = [item['id'] for item in products_to_print_list]
            products_map = {p.pk: p for p in Product.objects.filter(pk__in=product_ids)}
            
            final_products_for_template = []
            for item in products_to_print_list:
                product_id = item['id']
                quantity = item['quantity']
                
                if product_id in products_map:
                    product = products_map[product_id]
                    for _ in range(quantity):
                        final_products_for_template.append(product)
                else:
                    print(f"Предупреждение: Товар с ID {product_id} не найден.")

            if not final_products_for_template:
                return HttpResponse("Выбранные товары не найдены или не удалось получить их данные.", status=404)

            context = {
                'products': final_products_for_template,
                'current_datetime': datetime.now()
            }
            
            # ИСПРАВЛЕНО: Правильный путь к шаблону для ценников
            html_string = render_to_string('pricetags/pricetag_template.html', context)
            
            html = HTML(string=html_string)
            pdf_file = html.write_pdf()

            response = HttpResponse(pdf_file, content_type='application/pdf')
            response['Content-Disposition'] = 'inline; filename="pricetags.pdf"'
            return response

        except json.JSONDecodeError:
            return HttpResponse("Некорректный формат данных products_to_print.", status=400)
        except Exception as e:
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
            'retail_price': str(product.retail_price),
            'available_stock_quantity': product.get_available_stock_quantity,
        }
        return JsonResponse(data)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Товар не найден'}, status=404)
    except Exception as e:
        print(f"Ошибка при получении данных товара {product_id}: {e}")
        return JsonResponse({'error': f'Ошибка сервера: {e}'}, status=500)