// Ждем, пока вся страница загрузится
document.addEventListener('DOMContentLoaded', function() {

    // Эта функция будет пересчитывать доступное количество для конкретного товара
    function updateAvailableQuantityForProduct(productId) {
        if (!productId) {
            return;
        }

        // Находим все строки в таблице, которые относятся к этому товару
        const productRows = document.querySelectorAll(`.available-quantity-display[data-product-id="${productId}"]`);
        if (productRows.length === 0) {
            return;
        }

        // Берем данные, которые нам передал Python (они одинаковы для всех строк одного товара)
        const stock = parseInt(productRows[0].dataset.stockQuantity, 10);
        const reservedExternally = parseInt(productRows[0].dataset.reservedExternally, 10);

        // Считаем, сколько этого товара зарезервировано ПРЯМО СЕЙЧАС на странице
        let reservedOnThisPage = 0;
        const quantityInputs = document.querySelectorAll(`.order-item-quantity`);
        
        quantityInputs.forEach(input => {
            // Находим родительскую строку, чтобы проверить, тот ли это товар
            const row = input.closest('.dynamic-product_items');
            if (row) {
                const displaySpan = row.querySelector(`.available-quantity-display[data-product-id="${productId}"]`);
                // Если это строка с нашим товаром и она не помечена на удаление, считаем ее количество
                const deleteCheckbox = row.querySelector('input[id$="-DELETE"]');
                if (displaySpan && (!deleteCheckbox || !deleteCheckbox.checked)) {
                    reservedOnThisPage += parseInt(input.value, 10) || 0;
                }
            }
        });

        // Вычисляем новое доступное количество
        const newAvailable = stock - reservedExternally - reservedOnThisPage;

        // Обновляем цифру во всех строках для этого товара
        productRows.forEach(span => {
            span.textContent = newAvailable;
        });
    }

    // Эта функция будет запускать пересчет, когда что-то меняется
    function handleFormChange(event) {
        // Проверяем, что изменение произошло в поле количества
        if (event.target.classList.contains('order-item-quantity')) {
            const row = event.target.closest('.dynamic-product_items');
            if (row) {
                const displaySpan = row.querySelector('.available-quantity-display');
                if (displaySpan) {
                    const productId = displaySpan.dataset.productId;
                    updateAvailableQuantityForProduct(productId);
                }
            }
        }
    }
    
    // "Слушаем" все изменения на странице
    const form = document.getElementById('order_form');
    if (form) {
        form.addEventListener('change', handleFormChange);
        form.addEventListener('keyup', handleFormChange); // Для мгновенной реакции на ввод с клавиатуры
    }

    // Специальная магия для Django: слушаем, когда добавляется новая строка товара
    document.addEventListener('formset:added', function(event) {
        // event.target - это новая добавленная строка
        const newRow = event.target;
        // Навешиваем на нее наши обработчики
        newRow.addEventListener('change', handleFormChange);
        newRow.addEventListener('keyup', handleFormChange);

        // Также нужно обновить расчет, когда меняется сам товар в новой строке
        const productSelect = newRow.querySelector('select[id$="-product"]');
        if(productSelect) {
            // Используем jQuery, так как Select2 работает с ним
            (function($) {
                $(productSelect).on('select2:select', function(e) {
                    // Небольшая задержка, чтобы Django успел подгрузить данные
                    setTimeout(function() {
                         // Обновляем все товары, так как мы не знаем, какой был выбран раньше
                        const allProductIds = new Set([...document.querySelectorAll('.available-quantity-display')].map(s => s.dataset.productId));
                        allProductIds.forEach(id => updateAvailableQuantityForProduct(id));
                    }, 200);
                });
            })(django.jQuery);
        }
    });
});