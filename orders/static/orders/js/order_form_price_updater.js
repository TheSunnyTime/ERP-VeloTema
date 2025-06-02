// F:\CRM 2.0\ERP\orders\static\orders\js\order_form_price_updater.js
document.addEventListener('DOMContentLoaded', function() {
    // console.log('[DOM] ContentLoaded: Initializing order form updater and type determiner.');

    if (typeof django !== 'undefined' && typeof django.jQuery !== 'undefined') {
        const $ = django.jQuery;
        // console.log('[jQuery] Found. Initializing dynamic updates.');

        function parseFloatSafely(value) {
            if (typeof value === 'string') {
                value = value.replace(',', '.');
            }
            const parsed = parseFloat(value);
            return isNaN(parsed) ? 0 : parsed;
        }

        function updateOrderTotal() {
            let overallTotal = 0;
            $('#product_items-group .dynamic-product_items.form-row:not(.empty-form), #product_items-group tr.dynamic-product_items:not(.empty-form)').each(function() {
                const $row = $(this);
                const $productSelect = $row.find('select[name$="-product"]');
                if ($productSelect.length && $productSelect.val()) {
                    const $itemTotalEl = $row.find('td.field-display_item_total p, div.field-display_item_total div.readonly');
                    if ($itemTotalEl.length) {
                        overallTotal += parseFloatSafely($itemTotalEl.text());
                    }
                }
            });
            $('#service_items-group .dynamic-service_items.form-row:not(.empty-form), #service_items-group tr.dynamic-service_items:not(.empty-form)').each(function() {
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
            const $priceInput = $row.find('input[name$="-price_at_order"]');
            const $itemTotalDisplayElement = $row.find('td.field-display_item_total p, div.field-display_item_total div.readonly');

            if ($quantityInput.length && $priceInput.length && $itemTotalDisplayElement.length) {
                const quantity = parseInt($quantityInput.val(), 10);
                const price = parseFloatSafely($priceInput.val());

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
            const $row = $selectElement.closest('tr[class*="dynamic-"], .form-row[class*="dynamic-"]');

            if (!$row.length || $row.hasClass('empty-form')) {
                return;
            }

            const selectName = $selectElement.attr('name');
            if (!selectName) { return; } 
            
            const nameParts = selectName.split('-');
            if (nameParts.length < 2) { return; }

            const prefix = `${nameParts[0]}-${nameParts[1]}-`;
            const priceInputName = `${prefix}${priceFieldIdentifierInModel}`;
            const $priceInput = $row.find(`input[name="${priceInputName}"]`); // Поле <input> для цены
            
            // Элемент для отображения readonly цены (обычно <p> или <div> внутри td.field-price_at_order)
            const $priceReadonlyDisplay = $row.find(`td.field-${priceFieldIdentifierInModel} p, td.field-${priceFieldIdentifierInModel} div.readonly`);


            let $stockDisplayElement = $();
            if (stockJsonKey) {
                $stockDisplayElement = $row.find('td.field-get_current_stock p, div.field-get_current_stock div.readonly');
            }
            const $baseCostDisplayElement = $row.find('td.field-display_product_base_cost_price div.readonly, td.field-display_product_base_cost_price p');
            
            if (selectedId) {
                const fetchUrl = `${apiUrlPrefix}${selectedId}/`;
                // console.log(`[APIUpdater] Fetching from URL: ${fetchUrl} for select ${selectName}`);
                $.ajax({
                    url: fetchUrl,
                    type: 'GET',
                    success: function(data) {
                        // console.log(`[APIUpdater] Data received for ID ${selectedId} (URL: ${fetchUrl}):`, data);
                        let priceUpdated = false;
                        
                        // Пытаемся обновить поле <input> для цены, если оно существует и редактируемо
                        if ($priceInput.length && !$priceInput.is('[readonly]') && !$priceInput.is(':disabled')) {
                            console.log(`[APIUpdater] Found EDITABLE price input field: ${$priceInput.attr('name')}`);
                            if (data && typeof data[priceJsonKey] !== 'undefined' && data[priceJsonKey] !== null) {
                                const priceToSet = parseFloatSafely(data[priceJsonKey]).toFixed(2);
                                $priceInput.val(priceToSet);
                                console.log(`[APIUpdater] EDITABLE Price input field for ${selectName} UPDATED to: ${priceToSet}`);
                                priceUpdated = true;
                            } else {
                                $priceInput.val('0.00');
                                console.log(`[APIUpdater] Price data for ${selectName} not found or null. EDITABLE Price input set to 0.00. priceJsonKey was: ${priceJsonKey}`);
                            }
                        } 
                        
                        // Если input не был обновлен (например, его нет или он readonly), И есть элемент для readonly отображения
                        if (!priceUpdated && $priceReadonlyDisplay.length) {
                            console.log(`[APIUpdater] Price input NOT found or readonly. Found readonly display for ${priceFieldIdentifierInModel}.`);
                            if (data && typeof data[priceJsonKey] !== 'undefined' && data[priceJsonKey] !== null) {
                                const priceToSet = parseFloatSafely(data[priceJsonKey]).toFixed(2).replace('.', ',');
                                $priceReadonlyDisplay.text(priceToSet);
                                console.log(`[APIUpdater] READONLY Price display for ${selectName} UPDATED to: ${priceToSet}`);
                            } else {
                                $priceReadonlyDisplay.text('-');
                                console.log(`[APIUpdater] Price data for ${selectName} not found or null. READONLY Price display set to "-".`);
                            }
                        } else if (!priceUpdated && !$priceInput.length) { // Если не нашли ни input, ни readonly display
                            console.warn(`[APIUpdater] Price input field for ${selectName} (name: ${priceInputName}) AND its readonly display NOT found in row.`);
                        }


                        if (stockJsonKey && $stockDisplayElement.length) { 
                            if (typeof data[stockJsonKey] !== 'undefined' && data[stockJsonKey] !== null) {
                                let stock = parseInt(data[stockJsonKey], 10);
                                $stockDisplayElement.text(isNaN(stock) ? 'N/A' : stock + stockDisplaySuffix);
                            } else {
                                $stockDisplayElement.text('N/A');
                            }
                        }
                        if (costPriceJsonKey && $baseCostDisplayElement.length) {
                            if (data && typeof data[costPriceJsonKey] !== 'undefined' && data[costPriceJsonKey] !== null) {
                                $baseCostDisplayElement.text(parseFloatSafely(data[costPriceJsonKey]).toFixed(2));
                            } else {
                                $baseCostDisplayElement.text('---');
                            }
                        }
                        updateItemTotal($row);
                    },
                    error: function(xhr, status, error) {
                        console.error('[APIUpdater] Error fetching data for URL', fetchUrl, 'Error:', error, 'Status:', status);
                        if ($priceInput.length) $priceInput.val('0.00');
                        else if ($priceReadonlyDisplay.length) $priceReadonlyDisplay.text('-'); // Очищаем и readonly, если была ошибка
                        
                        if (stockJsonKey && $stockDisplayElement.length) $stockDisplayElement.text('Ошибка'); 
                        if (costPriceJsonKey && $baseCostDisplayElement.length) $baseCostDisplayElement.text('Ошибка');
                        updateItemTotal($row);
                    }
                });
            } else { 
                if ($priceInput.length) $priceInput.val('0.00');
                else if ($priceReadonlyDisplay.length) $priceReadonlyDisplay.text('-'); // Очищаем и readonly
                
                if (stockJsonKey && $stockDisplayElement.length) $stockDisplayElement.text(''); 
                if (costPriceJsonKey && $baseCostDisplayElement.length) $baseCostDisplayElement.text('---');
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
                // console.warn('[OrderTypeAPI] Order type select field AND readonly display not found. Exiting.');
                return;
            }
            
            let hasProducts = false;
            $('#product_items-group tr.dynamic-product_items:not(.empty-form), #product_items-group .dynamic-product_items.form-row:not(.empty-form)').each(function() {
                const $productSelect = $(this).find('select[name$="-product"]');
                if ($productSelect.length && $productSelect.val()) {
                    hasProducts = true;
                    return false; 
                }
            });

            let hasServices = false;
            $('#service_items-group tr.dynamic-service_items:not(.empty-form), #service_items-group .dynamic-service_items.form-row:not(.empty-form)').each(function() {
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
                    // console.log('[OrderTypeAPI] Raw API Response:', response); 
                    if (response.order_type_id !== null && typeof response.order_type_name !== 'undefined') {
                        let successfullyUpdatedSelect = false;
                        let typeActuallyChanged = false; 

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
                                    // console.log('[OrderTypeAPI] SELECT field updated to:', response.order_type_name, '(ID:', response.order_type_id, ')');
                                    typeActuallyChanged = true;
                                } 
                                successfullyUpdatedSelect = true;
                            } else {
                                // console.warn('[OrderTypeAPI] Option with value', response.order_type_id, 'NOT FOUND in #id_order_type select list.');
                            }
                        }
                        
                        if (!successfullyUpdatedSelect && $orderTypeReadonlyDiv.length) {
                            const currentTextInReadonly = $orderTypeReadonlyDiv.find('a').length ? $orderTypeReadonlyDiv.find('a').text().trim() : $orderTypeReadonlyDiv.text().trim();
                            if (currentTextInReadonly.toLowerCase() !== response.order_type_name.trim().toLowerCase()) {
                                const $linkInsideReadonly = $orderTypeReadonlyDiv.find('a');
                                if ($linkInsideReadonly.length) {
                                    $linkInsideReadonly.text(response.order_type_name);
                                } else {
                                    $orderTypeReadonlyDiv.text(response.order_type_name);
                                }
                                // console.log('[OrderTypeAPI] READONLY field text updated to:', response.order_type_name);
                                typeActuallyChanged = true;
                            }
                        }
                        
                        if (typeActuallyChanged) { 
                            $(document).trigger('order_type_dynamically_updated'); 
                            // console.log('[OrderTypeAPI] Triggered custom event "order_type_dynamically_updated".');
                        }

                    } else if (response.error) {
                        console.error('[OrderTypeAPI] Error from API:', response.error);
                    }
                },
                error: function(xhr, status, error) {
                    console.error('[OrderTypeAPI] AJAX Error fetching order type:', error, 'Status:', status);
                }
            });
        }

        // Обработчики событий
        $(document).on('change', '#product_items-group select[name$="-product"]', function() {
            fetchAndUpdatePriceAndStock(this, 'price_at_order', '/products-api/get-price/', 'retail_price', 'stock_quantity', 'cost_price');
        });
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
            let $row = $($rowFromArgs); 
            if (!($row && $row.length && typeof $row.find === 'function')) {
                const $lastRowInFormset = $('#' + formsetName + '-group .dynamic-' + formsetName + ':not(.empty-form)').last();
                if ($lastRowInFormset.length) {
                    $row = $lastRowInFormset;
                } else {
                    updateOrderTotal(); 
                    determineOrderTypeViaAPI();
                    return; 
                }
            }
            
            if ($row.length && typeof $row.find === 'function') { 
                const $selectsInRow = $row.find('select.admin-autocomplete');
                if ($selectsInRow.length && typeof $selectsInRow.select2 === 'function') {
                     $selectsInRow.each(function() {
                        const $select = $(this);
                        if (!$select.data('select2')) { 
                            $select.select2();
                        }
                     });
                }
            }
            updateOrderTotal(); 
            determineOrderTypeViaAPI(); 
        });
        $(document).on('formset:removed', function(event, $row, formsetName) {
            updateOrderTotal();
            determineOrderTypeViaAPI();
        });

        // Инициализация при загрузке страницы
        $('#product_items-group tr.dynamic-product_items:not(.empty-form), #product_items-group .dynamic-product_items.form-row:not(.empty-form)').each(function() {
            const $select = $(this).find('select[name$="-product"]');
            if ($select.length && $select.val()) {
                fetchAndUpdatePriceAndStock($select[0], 'price_at_order', '/products-api/get-price/', 'retail_price', 'stock_quantity', 'cost_price');
            }
        });
        $('#service_items-group tr.dynamic-service_items:not(.empty-form), #service_items-group .dynamic-service_items.form-row:not(.empty-form)').each(function() {
            const $select = $(this).find('select[name$="-service"]');
            if ($select.length && $select.val()) {
                 fetchAndUpdatePriceAndStock($select[0], 'price_at_order', '/orders-api/get-service-price/', 'price', null, null);
            }
        });
        
        setTimeout(function() {
            updateOrderTotal(); 
            determineOrderTypeViaAPI(); 
        }, 250); // Немного увеличил задержку для инициализации

        // console.log('[jQuery] All event listeners attached. Order form dynamic features active.');

    } else {
        console.warn('[Init] Django jQuery (django.jQuery) not found. Dynamic updates may not work correctly.');
    }
});