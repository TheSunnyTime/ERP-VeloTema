// F:\CRM 2.0\ERP\orders\static\orders\js\order_form_price_updater.js
document.addEventListener('DOMContentLoaded', function() {
    console.log('[DOM] ContentLoaded: Initializing order form updater and type determiner.');

    if (typeof django !== 'undefined' && typeof django.jQuery !== 'undefined') {
        const $ = django.jQuery;
        console.log('[jQuery] Found. Initializing dynamic updates.');

        function parseFloatSafely(value) {
            if (typeof value === 'string') {
                value = value.replace(',', '.');
            }
            const parsed = parseFloat(value);
            return isNaN(parsed) ? 0 : parsed;
        }

        function updateOrderTotal() {
            let overallTotal = 0;
            $('#product_items-group .dynamic-product_items.form-row:not(.empty-form)').each(function() {
                const $row = $(this);
                const $productSelect = $row.find('select[name$="-product"]');
                if ($productSelect.length && $productSelect.val()) {
                    const $itemTotalEl = $row.find('td.field-display_item_total p, div.field-display_item_total div.readonly');
                    if ($itemTotalEl.length) {
                        overallTotal += parseFloatSafely($itemTotalEl.text());
                    }
                }
            });
            $('#service_items-group .dynamic-service_items.form-row:not(.empty-form)').each(function() {
                const $row = $(this);
                const $serviceSelect = $row.find('select[name$="-service"]');
                if ($serviceSelect.length && $serviceSelect.val()) {
                    const $itemTotalEl = $row.find('td.field-display_item_total p, div.field-display_item_total div.readonly');
                    if ($itemTotalEl.length) {
                        overallTotal += parseFloatSafely($itemTotalEl.text());
                    }
                }
            });

            const $orderTotalDisplayElement = $('div.field-get_total_order_amount_display div.readonly');
            if ($orderTotalDisplayElement.length) {
                const totalStr = overallTotal.toFixed(2);
                $orderTotalDisplayElement.text(totalStr);
                // console.log('[OrderTotal] Overall order total updated to:', totalStr);
            } else {
                // console.warn('[OrderTotal] Display element for overall order total not found.');
            }
        }
        
        function updateItemTotal($row) {
            if (!$row || !$row.length || $row.hasClass('empty-form')) {
                // console.warn('[ItemTotal] updateItemTotal called with invalid or empty-form row.');
                return;
            }
            
            const $quantityInput = $row.find('input[name$="-quantity"]');
            const $priceInput = $row.find('input[name$="-price_at_order"]');
            const $itemTotalDisplayElement = $row.find('td.field-display_item_total p, div.field-display_item_total div.readonly');

            if ($quantityInput.length && $priceInput.length && $itemTotalDisplayElement.length) {
                const quantity = parseInt($quantityInput.val(), 10);
                const price = parseFloatSafely($priceInput.val());

                if (!isNaN(quantity) && quantity >= 0 && !isNaN(price)) {
                    const itemTotal = quantity * price;
                    const itemTotalStr = itemTotal.toFixed(2);
                    $itemTotalDisplayElement.text(itemTotalStr);
                    // console.log(`[ItemTotal] Item total updated for row (price: ${price}, qty: ${quantity}) to:`, itemTotalStr);
                } else {
                    $itemTotalDisplayElement.text('0.00');
                }
            }
            updateOrderTotal(); 
            determineOrderTypeViaAPI();
        }

        function fetchAndUpdatePriceAndStock(selectElement, priceFieldIdentifierInModel, apiUrlPrefix, priceJsonKey, stockJsonKey, stockDisplaySuffix = " шт.") {
            const $selectElement = $(selectElement);
            const selectedId = $selectElement.val();
            const $row = $selectElement.closest('tr.dynamic-' + $selectElement.attr('name').split('-')[0]); 

            if (!$row.length || $row.hasClass('empty-form')) {
                // console.warn('[APIUpdater] Could not find parent row or row is empty for select element:', selectElement.name);
                return;
            }

            const selectName = $selectElement.attr('name');
            if (!selectName) { return; } 
            const nameParts = selectName.split('-');
            if (nameParts.length < 2) { return; }

            const priceInputName = `${nameParts[0]}-${nameParts[1]}-${priceFieldIdentifierInModel}`;
            const $priceInput = $row.find(`input[name="${priceInputName}"]`);
            
            let $stockDisplayElement = $();
            if (stockJsonKey) {
                $stockDisplayElement = $row.find('td.field-get_current_stock p, div.field-get_current_stock div.readonly');
            }
            
            if (selectedId) {
                const fetchUrl = `${apiUrlPrefix}${selectedId}/`;
                $.ajax({
                    url: fetchUrl,
                    type: 'GET',
                    success: function(data) {
                        if ($priceInput.length) {
                            if (data && typeof data[priceJsonKey] !== 'undefined' && data[priceJsonKey] !== null) {
                                $priceInput.val(parseFloatSafely(data[priceJsonKey]).toFixed(2));
                            } else {
                                $priceInput.val('0.00');
                            }
                        }
                        if (stockJsonKey && data && $stockDisplayElement.length) { 
                            if (typeof data[stockJsonKey] !== 'undefined' && data[stockJsonKey] !== null) {
                                let stock = parseInt(data[stockJsonKey], 10);
                                $stockDisplayElement.text(isNaN(stock) ? 'N/A' : stock + stockDisplaySuffix);
                            } else {
                                $stockDisplayElement.text('N/A');
                            }
                        }
                        updateItemTotal($row);
                    },
                    error: function(xhr, status, error) {
                        console.error('[APIUpdater] Error fetching data:', error, 'Status:', status);
                        if ($priceInput.length) $priceInput.val('0.00');
                        if (stockJsonKey && $stockDisplayElement.length) $stockDisplayElement.text('Ошибка'); 
                        updateItemTotal($row);
                    }
                });
            } else { 
                if ($priceInput.length) $priceInput.val('0.00');
                if (stockJsonKey && $stockDisplayElement.length) $stockDisplayElement.text(''); 
                updateItemTotal($row);
            }
        }

        function determineOrderTypeViaAPI() {
    // console.log('[OrderTypeAPI] ENTERING determineOrderTypeViaAPI function'); // Можешь раскомментировать для отладки
    const $orderTypeSelect = $('#id_order_type'); // Это наш <select>
    // Это элемент, в котором Django обычно отображает readonly значение ForeignKey
    const $orderTypeReadonlyDiv = $('div.field-order_type div.readonly'); 

    // Не работаем на странице добавления нового заказа (/add/)
    if (window.location.pathname.includes('/add/')) {
        // console.log('[OrderTypeAPI] Skipping determination: isAddPage.');
        return;
    }

    // Если нет ни select, ни readonly div, то нечего обновлять
    if (!$orderTypeSelect.length && !$orderTypeReadonlyDiv.length) {
        console.warn('[OrderTypeAPI] Order type select field (#id_order_type) AND readonly display (div.field-order_type div.readonly) not found. Exiting.');
        return;
    }
    
    // Если поле select существует и оно disabled или readonly (атрибутом), то не пытаемся менять его через .val()
    // но текстовое поле $orderTypeReadonlyDiv все равно можем попытаться обновить.
    // Поэтому условие выхода if ($orderTypeSelect.is('[readonly]') || $orderTypeSelect.is(':disabled')) убираем отсюда,
    // логика будет ниже.

    // console.log('[OrderTypeAPI] Checking items to determine order type...');
    let hasProducts = false;
    $('#product_items-group tr.dynamic-product_items:not(.empty-form)').each(function() {
        const $productSelect = $(this).find('select[name$="-product"]');
        if ($productSelect.length && $productSelect.val()) {
            hasProducts = true;
            return false; 
        }
    });

    let hasServices = false;
    $('#service_items-group tr.dynamic-service_items:not(.empty-form)').each(function() {
        const $serviceSelect = $(this).find('select[name$="-service"]');
        if ($serviceSelect.length && $serviceSelect.val()) {
            hasServices = true;
            return false; 
        }
    });

    // console.log(`[OrderTypeAPI] Current state on form: hasProducts=${hasProducts}, hasServices=${hasServices}`);
    const apiUrl = '/orders-api/api/determine-order-type/'; // Убедись, что URL правильный

    $.ajax({
        url: apiUrl,
        type: 'GET',
        data: {
            'has_products': hasProducts,
            'has_services': hasServices
        },
        success: function(response) {
            // console.log('[OrderTypeAPI] Raw API Response:', response);
            if (response.order_type_id !== null && typeof response.order_type_name !== 'undefined') {
                let successfullyUpdatedSelect = false;

                // Пытаемся обновить <select> если он существует, не readonly и не disabled
                if ($orderTypeSelect.length && !$orderTypeSelect.is('[readonly]') && !$orderTypeSelect.is(':disabled')) {
                    // console.log('[OrderTypeAPI] Attempting to update #id_order_type. Current value:', $orderTypeSelect.val(), 'API wants to set ID:', response.order_type_id);
                    const $optionToSelect = $orderTypeSelect.find('option[value="' + response.order_type_id + '"]');
                    if ($optionToSelect.length > 0) {
                        // console.log('[OrderTypeAPI] Option with value', response.order_type_id, '("' + $optionToSelect.text() + '") found in select list.');
                        if (String($orderTypeSelect.val()) !== String(response.order_type_id)) {
                            $orderTypeSelect.val(response.order_type_id);
                            // console.log('[OrderTypeAPI] Value set via .val(). New #id_order_type value:', $orderTypeSelect.val());
                            if ($orderTypeSelect.data('select2')) {
                                $orderTypeSelect.trigger('change.select2');
                            } else {
                                $orderTypeSelect.trigger('change'); 
                            }
                            console.log('[OrderTypeAPI] SELECT field updated to:', response.order_type_name, '(ID:', response.order_type_id, ')');
                            successfullyUpdatedSelect = true;
                        } else {
                            // console.log('[OrderTypeAPI] SELECT field is already set to ID:', response.order_type_id, 'Name:', response.order_type_name);
                            successfullyUpdatedSelect = true; // Считаем успешным, т.к. значение уже верное
                        }
                    } else {
                        console.warn('[OrderTypeAPI] Option with value', response.order_type_id, 'NOT FOUND in #id_order_type select list.');
                    }
                } else if ($orderTypeSelect.length) {
                    console.log('[OrderTypeAPI] #id_order_type select found, but it is readonly or disabled. Will try to update text if possible.');
                }

                // Если <select> не был обновлен (или его нет), и есть readonly-контейнер, обновляем текст в нем
                if (!successfullyUpdatedSelect && $orderTypeReadonlyDiv.length) {
                    // Django для readonly ForeignKey часто делает ссылку внутри <div class="readonly">
                    // <div class="readonly"><a href="...">Имя типа</a></div>
                    // Нам нужно обновить текст ссылки или сам текст div.readonly
                    const $linkInsideReadonly = $orderTypeReadonlyDiv.find('a');
                    if ($linkInsideReadonly.length) {
                        // Обновляем текст ссылки, но не сам href, т.к. ID может не совпадать с тем, на что должна вести ссылка, если тип изменился
                        $linkInsideReadonly.text(response.order_type_name);
                        console.log('[OrderTypeAPI] READONLY field (link text) updated to:', response.order_type_name);
                    } else {
                        // Если ссылки нет, просто обновляем текст div.readonly
                        $orderTypeReadonlyDiv.text(response.order_type_name);
                        console.log('[OrderTypeAPI] READONLY field (div text) updated to:', response.order_type_name);
                    }
                } else if (!successfullyUpdatedSelect && !$orderTypeReadonlyDiv.length) {
                    console.warn('[OrderTypeAPI] Could not update order type display: neither editable select nor readonly div found/updated.');
                }

            } else if (response.error) {
                console.error('[OrderTypeAPI] Error from API:', response.error);
            } else {
                console.warn('[OrderTypeAPI] Received incomplete data from API:', response);
            }
        },
        error: function(xhr, status, error) {
            console.error('[OrderTypeAPI] AJAX Error fetching order type:', error, 'Status:', status);
        }
    });
}

        // Обработчики событий
        $(document).on('change', '#product_items-group select[name$="-product"]', function() {
            fetchAndUpdatePriceAndStock(this, 'price_at_order', '/products-api/get-price/', 'retail_price', 'stock_quantity');
        });
        $(document).on('change', '#service_items-group select[name$="-service"]', function() {
            fetchAndUpdatePriceAndStock(this, 'price_at_order', '/orders-api/get-service-price/', 'price', null); 
        });
        $(document).on('input change', 
                       '#product_items-group input[name$="-quantity"], #service_items-group input[name$="-quantity"]', 
                       function() {
            const $row = $(this).closest('tr.dynamic-' + $(this).attr('name').split('-')[0]);
            updateItemTotal($row);
        });

        $(document).on('formset:added', function(event, $rowFromArgs, formsetName) {
            const $row = $($rowFromArgs); // Убедимся, что это jQuery объект, если $rowFromArgs - это DOM элемент
                                      // или используем $(event.target).closest('tr.dynamic-...') если $rowFromArgs не всегда корректен

            // console.log(`[Listener] Formset row added to ${formsetName}.`);
            
            if ($row && $row.length && typeof $row.find === 'function') {
                const $selectsInRow = $row.find('select.admin-autocomplete');
                if ($selectsInRow.length && typeof $selectsInRow.select2 === 'function') {
                     $selectsInRow.each(function() {
                        const $select = $(this);
                        if (!$select.data('select2')) { 
                            // console.log('[Listener] Initializing select2 for new row:', $select.attr('id'));
                            $select.select2();
                        }
                     });
                }
            } else {
                 console.warn(`[Listener] 'formset:added' event for ${formsetName}, but could not get a valid $row.`);
            }
            updateOrderTotal(); 
            determineOrderTypeViaAPI(); 
        });
        $(document).on('formset:removed', function(event, $row, formsetName) {
            // console.log(`[Listener] Formset row removed from ${formsetName}.`);
            updateOrderTotal();
            determineOrderTypeViaAPI();
        });

        // Инициализация при загрузке страницы
        updateOrderTotal(); 
        determineOrderTypeViaAPI(); 

        console.log('[jQuery] All event listeners attached. Order form dynamic features active.');

    } else {
        console.warn('[Init] Django jQuery (django.jQuery) not found. Dynamic updates may not work correctly.');
    }
});