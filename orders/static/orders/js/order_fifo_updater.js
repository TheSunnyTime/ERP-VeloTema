// ERP/orders/static/orders/js/order_fifo_updater.js

if (typeof django !== 'undefined' && typeof django.jQuery !== 'undefined') {
    (function($) {
        $(document).ready(function() {
            
        var orderStatusMarker = document.getElementById('order-status-marker');
        var orderStatus = orderStatusMarker ? orderStatusMarker.value : null;
        var disabledStatuses = ['issued', 'cancelled']; // ключи такие же, как в Order.STATUS_ISSUED и Order.STATUS_CANCELLED

        if (orderStatus && disabledStatuses.indexOf(orderStatus) !== -1) {
            console.log('[OrderJS] Динамика отключена для статуса: ' + orderStatus);
            return;
        }

            console.log('[OrderFIFOUpdater] Initializing FIFO cost updater...');

            function updateFifoCostForInlineRow($row) {
                if (!$row || !$row.length || $row.hasClass('empty-form')) {
                    return;
                }

                const $productSelect = $row.find('select[name$="-product"]');
                const $quantityInput = $row.find('input[name$="-quantity"]');
                
                // Найдем поле, где будем отображать FIFO себестоимость.
                // Это существующее поле cost_price_at_sale, которое сейчас readonly.
                // Мы будем обновлять его текстовое представление или значение, если это input.
                // В твоем OrderProductItemInline cost_price_at_sale находится в readonly_fields.
                // Значит, это будет <p> или <div> внутри td.field-cost_price_at_sale.
                const $fifoCostDisplayElement = $row.find('td.field-cost_price_at_sale div.readonly, td.field-cost_price_at_sale p');
                // Если это input (на случай если оно не readonly для суперюзера, например)
                const $fifoCostInputElement = $row.find('input[name$="-cost_price_at_sale"]');


                if (!$productSelect.length || !$quantityInput.length) {
                    console.warn('[OrderFIFOUpdater] Product select or quantity input not found in row:', $row.attr('id'));
                    if ($fifoCostDisplayElement.length) $fifoCostDisplayElement.text('-');
                    if ($fifoCostInputElement.length) $fifoCostInputElement.val('');
                    return;
                }

                const productId = $productSelect.val();
                const quantity = $quantityInput.val();

                if (productId && quantity && parseInt(quantity, 10) > 0) {
                    // console.log(`[OrderFIFOUpdater] Requesting FIFO for Product ID: ${productId}, Quantity: ${quantity}`);
                    $.ajax({
                        url: '/orders-api/calculate-fifo-cost/', // Убедись, что URL правильный
                        type: 'GET',
                        data: {
                            'product_id': productId,
                            'quantity': quantity
                        },
                        success: function(response) {
                            // console.log('[OrderFIFOUpdater] API Response:', response);
                            let displayValue = '-';
                            if (response.sufficient_stock && response.estimated_fifo_cost) {
                                displayValue = parseFloat(response.estimated_fifo_cost).toFixed(2).replace('.', ',');
                            } else if (!response.sufficient_stock) {
                                displayValue = 'Недостат.'; // Или более подробное сообщение
                                console.warn(`[OrderFIFOUpdater] Insufficient stock for Product ID ${productId}. Available: ${response.available_stock}`);
                            }

                            if ($fifoCostDisplayElement.length) {
                                $fifoCostDisplayElement.text(displayValue);
                            }
                            if ($fifoCostInputElement.length) { // Если это input, тоже обновим
                                $fifoCostInputElement.val(response.sufficient_stock ? response.estimated_fifo_cost : '');
                            }
                        },
                        error: function(xhr, status, error) {
                            console.error('[OrderFIFOUpdater] AJAX Error fetching FIFO cost:', error, 'Status:', status);
                            if ($fifoCostDisplayElement.length) $fifoCostDisplayElement.text('Ошибка');
                            if ($fifoCostInputElement.length) $fifoCostInputElement.val('');
                        }
                    });
                } else {
                    // Если товар не выбран или количество 0/пусто, очищаем поле FIFO
                    if ($fifoCostDisplayElement.length) $fifoCostDisplayElement.text('-');
                    if ($fifoCostInputElement.length) $fifoCostInputElement.val('');
                }
            }

            // Обработчики событий для инлайна товаров (OrderProductItemInline)
            // 1. При изменении выбранного товара
            $(document).on('change', '#product_items-group select[name$="-product"]', function() {
                const $row = $(this).closest('tr.dynamic-product_items, .form-row.dynamic-product_items');
                updateFifoCostForInlineRow($row);
            });

            // 2. При изменении количества товара
            $(document).on('input change', '#product_items-group input[name$="-quantity"]', function() {
                const $row = $(this).closest('tr.dynamic-product_items, .form-row.dynamic-product_items');
                updateFifoCostForInlineRow($row);
            });

            // 3. При добавлении новой строки в инлайн
            $(document).on('formset:added', function(event, $rowFromArgs, formsetName) {
                if (formsetName === 'product_items') { // Только для инлайна товаров
                    const $row = $($rowFromArgs);
                    if ($row.length && typeof $row.find === 'function') {
                        // Для новой строки поля будут пустыми, updateFifoCostForInlineRow очистит FIFO поле
                        updateFifoCostForInlineRow($row);
                    }
                }
            });

            // 4. Инициализация для уже существующих строк при загрузке страницы
            $('#product_items-group tr.dynamic-product_items:not(.empty-form), #product_items-group .dynamic-product_items.form-row:not(.empty-form)').each(function() {
                updateFifoCostForInlineRow($(this));
            });

            console.log('[OrderFIFOUpdater] FIFO cost updater initialized.');
        });
    })(django.jQuery);
} else {
    console.error("[OrderFIFOUpdater] django.jQuery is not available.");
}