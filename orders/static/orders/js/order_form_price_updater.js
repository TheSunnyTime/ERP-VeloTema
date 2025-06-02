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
            }
        }
        
        function updateItemTotal($row) {
            if (!$row || !$row.length || $row.hasClass('empty-form')) {
                return;
            }
            
            const $quantityInput = $row.find('input[name$="-quantity"]');
            const $priceInput = $row.find('input[name$="-price_at_order"]'); // Цена продажи
            const $itemTotalDisplayElement = $row.find('td.field-display_item_total p, div.field-display_item_total div.readonly');

            if ($quantityInput.length && $priceInput.length && $itemTotalDisplayElement.length) {
                const quantity = parseInt($quantityInput.val(), 10);
                const price = parseFloatSafely($priceInput.val()); // Цена продажи

                if (!isNaN(quantity) && quantity >= 0 && !isNaN(price)) {
                    const itemTotal = quantity * price;
                    const itemTotalStr = itemTotal.toFixed(2);
                    $itemTotalDisplayElement.text(itemTotalStr);
                } else {
                    $itemTotalDisplayElement.text('0.00');
                }
            }
            updateOrderTotal(); 
            determineOrderTypeViaAPI();
        }

        function fetchAndUpdatePriceAndStock(selectElement, priceFieldIdentifierInModel, apiUrlPrefix, priceJsonKey, stockJsonKey, costPriceJsonKey = 'cost_price', stockDisplaySuffix = " шт.") {
            const $selectElement = $(selectElement);
            const selectedId = $selectElement.val();
            // Более надежный поиск строки, который работает и для product_items и для service_items
            const $row = $selectElement.closest('tr[class*="dynamic-"], .form-row[class*="dynamic-"]');


            if (!$row.length || $row.hasClass('empty-form')) {
                console.warn('[APIUpdater] Could not find parent row or row is empty for select element:', selectElement.name);
                return;
            }

            const selectName = $selectElement.attr('name');
            if (!selectName) { return; } 
            const nameParts = selectName.split('-');
            if (nameParts.length < 2) { return; }

            const priceInputName = `${nameParts[0]}-${nameParts[1]}-${priceFieldIdentifierInModel}`;
            const $priceInput = $row.find(`input[name="${priceInputName}"]`); // Цена продажи
            
            let $stockDisplayElement = $();
            if (stockJsonKey) { // Только для товаров, у услуг stockJsonKey будет null
                $stockDisplayElement = $row.find('td.field-get_current_stock p, div.field-get_current_stock div.readonly');
            }

            // --- НОВОЕ: Поиск элемента для отображения базовой себестоимости ---
            // Имя поля должно совпадать с тем, что ты определишь в OrderProductItemInline (readonly_fields)
            // Например, 'display_product_base_cost_price'
            const $baseCostDisplayElement = $row.find('td.field-display_product_base_cost_price div.readonly, td.field-display_product_base_cost_price p');
            // --- КОНЕЦ НОВОГО ---
            
            if (selectedId) {
                const fetchUrl = `${apiUrlPrefix}${selectedId}/`;
                console.log('[APIUpdater] Fetching from URL:', fetchUrl);
                $.ajax({
                    url: fetchUrl,
                    type: 'GET',
                    success: function(data) {
                        console.log('[APIUpdater] Data received:', data);
                        if ($priceInput.length) { // Обновляем цену продажи
                            if (data && typeof data[priceJsonKey] !== 'undefined' && data[priceJsonKey] !== null) {
                                $priceInput.val(parseFloatSafely(data[priceJsonKey]).toFixed(2));
                            } else {
                                $priceInput.val('0.00');
                            }
                        }
                        if (stockJsonKey && data && $stockDisplayElement.length) { // Обновляем остаток (только для товаров)
                            if (typeof data[stockJsonKey] !== 'undefined' && data[stockJsonKey] !== null) {
                                let stock = parseInt(data[stockJsonKey], 10);
                                $stockDisplayElement.text(isNaN(stock) ? 'N/A' : stock + stockDisplaySuffix);
                            } else {
                                $stockDisplayElement.text('N/A');
                            }
                        }

                        // --- НОВОЕ: Обновление отображения базовой себестоимости (Product.cost_price) ---
                        if (costPriceJsonKey && $baseCostDisplayElement.length) { // costPriceJsonKey будет 'cost_price' для товаров
                            if (data && typeof data[costPriceJsonKey] !== 'undefined' && data[costPriceJsonKey] !== null) {
                                $baseCostDisplayElement.text(parseFloatSafely(data[costPriceJsonKey]).toFixed(2));
                                console.log('[APIUpdater] Base cost price updated to:', data[costPriceJsonKey]);
                            } else {
                                $baseCostDisplayElement.text('---');
                                console.log('[APIUpdater] Base cost price data not found or null.');
                            }
                        } else if (costPriceJsonKey) {
                            console.warn('[APIUpdater] Base cost display element not found for class .field-display_product_base_cost_price');
                        }
                        // --- КОНЕЦ НОВОГО ---

                        updateItemTotal($row);
                    },
                    error: function(xhr, status, error) {
                        console.error('[APIUpdater] Error fetching data:', error, 'Status:', status, 'URL:', fetchUrl);
                        if ($priceInput.length) $priceInput.val('0.00');
                        if (stockJsonKey && $stockDisplayElement.length) $stockDisplayElement.text('Ошибка'); 
                        // --- НОВОЕ: Очистка при ошибке ---
                        if (costPriceJsonKey && $baseCostDisplayElement.length) $baseCostDisplayElement.text('Ошибка');
                        // --- КОНЕЦ НОВОГО ---
                        updateItemTotal($row);
                    }
                });
            } else { // Если товар/услуга не выбраны (очищено поле)
                if ($priceInput.length) $priceInput.val('0.00');
                if (stockJsonKey && $stockDisplayElement.length) $stockDisplayElement.text(''); 
                // --- НОВОЕ: Очистка при сбросе выбора ---
                if (costPriceJsonKey && $baseCostDisplayElement.length) $baseCostDisplayElement.text('---');
                // --- КОНЕЦ НОВОГО ---
                updateItemTotal($row);
            }
        }

        function determineOrderTypeViaAPI() {
            const $orderTypeSelect = $('#id_order_type'); 
            const $orderTypeReadonlyDiv = $('div.field-order_type div.readonly'); 

            if (window.location.pathname.includes('/add/')) {
                return;
            }

            if (!$orderTypeSelect.length && !$orderTypeReadonlyDiv.length) {
                console.warn('[OrderTypeAPI] Order type select field AND readonly display not found. Exiting.');
                return;
            }
            
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

            const apiUrl = '/orders-api/api/determine-order-type/'; 

            $.ajax({
                url: apiUrl,
                type: 'GET',
                data: {
                    'has_products': hasProducts,
                    'has_services': hasServices
                },
                success: function(response) {
                    if (response.order_type_id !== null && typeof response.order_type_name !== 'undefined') {
                        let successfullyUpdatedSelect = false;
                        let typeUpdated = false;

                        if ($orderTypeSelect.length && !$orderTypeSelect.is('[readonly]') && !$orderTypeSelect.is(':disabled')) {
                            const $optionToSelect = $orderTypeSelect.find('option[value="' + response.order_type_id + '"]');
                            if ($optionToSelect.length > 0) {
                                if (String($orderTypeSelect.val()) !== String(response.order_type_id)) {
                                    $orderTypeSelect.val(response.order_type_id);
                                    if ($orderTypeSelect.data('select2')) {
                                        $orderTypeSelect.trigger('change.select2');
                                    } else {
                                        $orderTypeSelect.trigger('change'); 
                                    }
                                    console.log('[OrderTypeAPI] SELECT field updated to:', response.order_type_name, '(ID:', response.order_type_id, ')');
                                    typeUpdated = true;
                                } 
                                successfullyUpdatedSelect = true;
                            } else {
                                console.warn('[OrderTypeAPI] Option with value', response.order_type_id, 'NOT FOUND in #id_order_type select list.');
                            }
                        }
                        
                        if (!successfullyUpdatedSelect && $orderTypeReadonlyDiv.length) {
                            const currentText = $orderTypeReadonlyDiv.find('a').length ? $orderTypeReadonlyDiv.find('a').text() : $orderTypeReadonlyDiv.text();
                            if (currentText.trim() !== response.order_type_name.trim()) {
                                const $linkInsideReadonly = $orderTypeReadonlyDiv.find('a');
                                if ($linkInsideReadonly.length) {
                                    $linkInsideReadonly.text(response.order_type_name);
                                } else {
                                    $orderTypeReadonlyDiv.text(response.order_type_name);
                                }
                                console.log('[OrderTypeAPI] READONLY field text updated to:', response.order_type_name);
                                typeUpdated = true;
                            }
                        }
                        
                        if (typeUpdated) { // Генерируем событие, только если тип действительно изменился
                            $(document).trigger('order_type_dynamically_updated'); 
                            console.log('[OrderTypeAPI] Triggered custom event "order_type_dynamically_updated".');
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
        // Для товаров: передаем 'cost_price' как ключ для базовой себестоимости
        $(document).on('change', '#product_items-group select[name$="-product"]', function() {
            fetchAndUpdatePriceAndStock(this, 'price_at_order', '/products-api/get-price/', 'retail_price', 'stock_quantity', 'cost_price');
        });
        // Для услуг: costPriceJsonKey и stockJsonKey равны null, чтобы эти поля не обновлялись
        $(document).on('change', '#service_items-group select[name$="-service"]', function() {
            fetchAndUpdatePriceAndStock(this, 'price_at_order', '/orders-api/get-service-price/', 'price', null, null); 
        });

        $(document).on('input change', 
                       '#product_items-group input[name$="-quantity"], #service_items-group input[name$="-quantity"]', 
                       function() {
            const $row = $(this).closest('tr[class*="dynamic-"], .form-row[class*="dynamic-"]');
            updateItemTotal($row);
        });

        $(document).on('formset:added', function(event, $rowFromArgs, formsetName) {
            const $row = $($rowFromArgs); 
            if ($row && $row.length && typeof $row.find === 'function') {
                const $selectsInRow = $row.find('select.admin-autocomplete');
                if ($selectsInRow.length && typeof $selectsInRow.select2 === 'function') {
                     $selectsInRow.each(function() {
                        const $select = $(this);
                        if (!$select.data('select2')) { 
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
            updateOrderTotal();
            determineOrderTypeViaAPI();
        });

        // Инициализация при загрузке страницы
        // Выполняем для всех существующих строк товаров и услуг
        $('#product_items-group tr.dynamic-product_items:not(.empty-form)').each(function() {
            const $select = $(this).find('select[name$="-product"]');
            if ($select.length && $select.val()) { // Если товар уже выбран
                fetchAndUpdatePriceAndStock($select[0], 'price_at_order', '/products-api/get-price/', 'retail_price', 'stock_quantity', 'cost_price');
            }
            updateItemTotal($(this)); // Обновить "Сумму по позиции"
        });
        $('#service_items-group tr.dynamic-service_items:not(.empty-form)').each(function() {
            const $select = $(this).find('select[name$="-service"]');
            if ($select.length && $select.val()) { // Если услуга уже выбрана
                 fetchAndUpdatePriceAndStock($select[0], 'price_at_order', '/orders-api/get-service-price/', 'price', null, null);
            }
            updateItemTotal($(this)); // Обновить "Сумму по позиции"
        });
        
        updateOrderTotal(); // Обновить общую сумму заказа
        determineOrderTypeViaAPI(); // Определить тип заказа

        console.log('[jQuery] All event listeners attached. Order form dynamic features active.');

    } else {
        console.warn('[Init] Django jQuery (django.jQuery) not found. Dynamic updates may not work correctly.');
    }
});