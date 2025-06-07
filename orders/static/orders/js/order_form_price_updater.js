// F:\CRM 2.0\ERP\orders\static\orders\js\order_form_price_updater.js
document.addEventListener('DOMContentLoaded', function() {
    // console.log('[DOM] ContentLoaded: Initializing order form updater and type determiner.');

    if (typeof django !== 'undefined' && typeof django.jQuery !== 'undefined') {
        const $ = django.jQuery;
        console.log('[PriceUpdater] Initializing...');

        // СНАЧАЛА ВСЕ ОПРЕДЕЛЕНИЯ ФУНКЦИЙ:

        function parseFloatSafely(value) {
            if (typeof value === 'string') {
                value = value.replace(',', '.'); 
            }
            const parsed = parseFloat(value);
            return isNaN(parsed) ? 0 : parsed;
        }

        function determineOrderTypeViaAPI() {
            const $orderTypeSelect = $('#id_order_type');
            const $orderTypeReadonlyDiv = $('div.field-order_type div.readonly');

            if (window.location.pathname.includes('/add/')) {
                // console.log('[OrderTypeAPI] Add page, skipping API call for now.');
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
                    return false; // Прерываем цикл .each
                }
            });

            let hasServices = false;
            $('#service_items-group tr.dynamic-service_items:not(.empty-form), #service_items-group .dynamic-service_items.form-row:not(.empty-form)').each(function() {
                const $serviceSelect = $(this).find('select[name$="-service"]');
                if ($serviceSelect.length && $serviceSelect.val()) {
                    hasServices = true;
                    return false; // Прерываем цикл .each
                }
            });

            const apiUrl = '/orders-api/api/determine-order-type/';
            // console.log(`[OrderTypeAPI] Calling API. Has Products: ${hasProducts}, Has Services: ${hasServices}`);

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
                        let successfullyUpdatedDisplay = false;
                        let typeActuallyChanged = false;

                        if ($orderTypeSelect.length && !$orderTypeSelect.is('[readonly]') && !$orderTypeSelect.is(':disabled')) {
                            const $optionToSelect = $orderTypeSelect.find('option[value="' + response.order_type_id + '"]');
                            if ($optionToSelect.length > 0) {
                                if (String($orderTypeSelect.val()) !== String(response.order_type_id)) {
                                    $orderTypeSelect.val(response.order_type_id);
                                    if ($orderTypeSelect.data('select2')) { // Если используется Select2
                                        $orderTypeSelect.trigger('change.select2');
                                    } else {
                                        $orderTypeSelect.trigger('change');
                                    }
                                    // console.log('[OrderTypeAPI] SELECT field updated to:', response.order_type_name, '(ID:', response.order_type_id, ')');
                                    typeActuallyChanged = true;
                                }
                                successfullyUpdatedDisplay = true;
                            } else {
                                // console.warn('[OrderTypeAPI] Option with value', response.order_type_id, 'NOT FOUND in #id_order_type select list.');
                            }
                        }

                        if (!successfullyUpdatedDisplay && $orderTypeReadonlyDiv.length) {
                            const currentTextInReadonly = $orderTypeReadonlyDiv.find('a').length ? $orderTypeReadonlyDiv.find('a').text().trim() : $orderTypeReadonlyDiv.text().trim();
                            if (currentTextInReadonly.toLowerCase() !== response.order_type_name.trim().toLowerCase()) {
                                const $linkInsideReadonly = $orderTypeReadonlyDiv.find('a');
                                if ($linkInsideReadonly.length) { // Если внутри есть ссылка (например, на модель типа заказа)
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
                $orderTotalDisplayElement.text(totalStr.replace('.', ',')); 
            }
        }
        
        function updateItemTotal($row) {
            if (!$row || !$row.length || $row.hasClass('empty-form')) {
                return;
            }
            
            const $quantityInput = $row.find('input[name$="-quantity"]');
            const $priceInput = $row.find('input[name$="-price_at_order"]');
            const $priceReadonlyElement = $row.find('td.field-price_at_order p'); 
            const $itemTotalDisplayElement = $row.find('td.field-display_item_total p, div.field-display_item_total div.readonly');

            if ($itemTotalDisplayElement.length) {
                let quantityText, priceText;

                if ($quantityInput.length) {
                    quantityText = $quantityInput.val();
                } else {
                    quantityText = '0';
                }

                if ($priceInput.length && !$priceInput.is('[readonly]') && $priceInput.is(':visible')) {
                    priceText = $priceInput.val();
                } 
                else if ($priceReadonlyElement.length) { 
                    priceText = $priceReadonlyElement.text();
                } 
                else {
                    priceText = '0.00';
                }
                
                const quantity = parseInt(quantityText, 10); 
                const price = parseFloatSafely(priceText);

                if (!isNaN(quantity) && quantity >= 0 && !isNaN(price) && price >= 0) {
                    const itemTotal = quantity * price;
                    const itemTotalStr = itemTotal.toFixed(2);
                    $itemTotalDisplayElement.text(itemTotalStr.replace('.', ','));
                } else {
                    $itemTotalDisplayElement.text('0,00');
                }
            }
            updateOrderTotal(); 
            determineOrderTypeViaAPI();
        }

        // ИЗМЕНЕН ПОРЯДОК АРГУМЕНТОВ: isUserInteraction теперь ПЕРЕД stockDisplaySuffix
        function fetchAndUpdatePriceAndStock(selectElement, priceFieldIdentifierInModel, apiUrlPrefix, priceJsonKey, stockJsonKey, costPriceJsonKey = 'cost_price', isUserInteraction = false, stockDisplaySuffix = " шт.") {
            const $selectElement = $(selectElement);
            const selectedId = $selectElement.val();
            const $row = $selectElement.closest('tr[class*="dynamic-"], .form-row[class*="dynamic-"]');

            if (!$row.length || $row.hasClass('empty-form')) return;

            const selectName = $selectElement.attr('name');
            if (!selectName) return; 
            
            const nameParts = selectName.split('-');
            if (nameParts.length < 2) return;

            const prefix = `${nameParts[0]}-${nameParts[1]}-`;
            const priceInputName = `${prefix}${priceFieldIdentifierInModel}`;
            const $priceInput = $row.find(`input[name="${priceInputName}"]`);
            const $priceReadonlyDisplay = $row.find(`td.field-${priceFieldIdentifierInModel} p`);
            
            console.log(`[fetchAndUpdatePriceAndStock] Called for: ${selectName}, Selected ID: ${selectedId}, isUserInteraction: ${isUserInteraction}`);

            if ($priceInput.length && isUserInteraction) {
                const oldManualPriceFlag = $priceInput.attr('data-manual-price');
                $priceInput.removeAttr('data-manual-price');
                console.log(`[fetchAndUpdatePriceAndStock] User interaction: Cleared data-manual-price for ${priceInputName}. Was: ${oldManualPriceFlag}`);
            }

            let $stockDisplayElement = $();
            if (stockJsonKey) { $stockDisplayElement = $row.find(`td.field-get_current_stock p, div.field-get_current_stock div.readonly`); }
            const $baseCostDisplayElement = $row.find(`td.field-display_product_base_cost_price p, div.field-display_product_base_cost_price div.readonly`);
            
            if (selectedId) {
                const fetchUrl = `${apiUrlPrefix}${selectedId}/`;
                $.ajax({
                    url: fetchUrl,
                    type: 'GET',
                    success: function(data) {
                        let priceUpdatedViaInput = false;
                        if ($priceInput.length && !$priceInput.is('[readonly]') && !$priceInput.is(':disabled')) {
                            const currentManualPriceFlag = $priceInput.attr('data-manual-price'); 
                            const isManuallySet = currentManualPriceFlag === 'true';
                            console.log(`[fetchAndUpdatePriceAndStock] For ${priceInputName} - isManuallySet: ${isManuallySet} (Flag value: ${currentManualPriceFlag})`);
                            if (!isManuallySet) { 
                                if (data && typeof data[priceJsonKey] !== 'undefined' && data[priceJsonKey] !== null) {
                                    const priceToSet = parseFloatSafely(data[priceJsonKey]).toFixed(2);
                                    $priceInput.val(priceToSet);
                                    console.log(`[fetchAndUpdatePriceAndStock] Price for ${priceInputName} SET to ${priceToSet} (API)`);
                                } else {
                                    $priceInput.val('0.00');
                                    console.log(`[fetchAndUpdatePriceAndStock] Price for ${priceInputName} SET to 0.00 (API, no data)`);
                                }
                            } else {
                                console.log(`[fetchAndUpdatePriceAndStock] Price for ${priceInputName} was manually set. API update SKIPPED. Current value: ${$priceInput.val()}`);
                            }
                            priceUpdatedViaInput = true; 
                        } 
                        if ((!priceUpdatedViaInput || !$priceInput.length) && $priceReadonlyDisplay.length) {
                            if (data && typeof data[priceJsonKey] !== 'undefined' && data[priceJsonKey] !== null) {
                                const priceToSetForDisplay = parseFloatSafely(data[priceJsonKey]).toFixed(2).replace('.', ',');
                                $priceReadonlyDisplay.text(priceToSetForDisplay);
                            } else {
                                $priceReadonlyDisplay.text('-');
                            }
                        } else if (!priceUpdatedViaInput && !$priceInput.length && !$priceReadonlyDisplay.length) {
                             console.warn(`[APIUpdater] Price input/readonly display for ${selectName} (name: ${priceInputName} or td.field-${priceFieldIdentifierInModel} p) NOT found in row.`);
                        }
                        
                        if (stockJsonKey && $stockDisplayElement.length) { 
                            if (typeof data[stockJsonKey] !== 'undefined' && data[stockJsonKey] !== null) {
                                let stockFromApi = parseInt(data[stockJsonKey], 10);
                                
                                console.log(`[StockUpdater] Product ID: ${selectedId}, Stock from API (raw): ${data[stockJsonKey]}, Parsed stockFromApi: ${stockFromApi}, Type: ${typeof stockFromApi}`);
                                console.log(`[StockUpdater] stockDisplaySuffix: "${stockDisplaySuffix}", Type: ${typeof stockDisplaySuffix}`);
                                
                                let valueForText = stockFromApi; 
                                let suffixForText = stockDisplaySuffix; 

                                console.log(`[StockUpdater] BEFORE CONCAT: valueForText = ${valueForText} (type: ${typeof valueForText}), suffixForText = "${suffixForText}" (type: ${typeof suffixForText})`);

                                let textToDisplay = isNaN(valueForText) ? 'N/A' : String(valueForText) + suffixForText; 
                                
                                console.log(`[StockUpdater] Text to display for stock (AFTER CONCAT): "${textToDisplay}"`); 
                                
                                $stockDisplayElement.text(textToDisplay);
                            } else {
                                $stockDisplayElement.text('N/A');
                            }
                        }

                        if (costPriceJsonKey && $baseCostDisplayElement.length) {
                            if (data && typeof data[costPriceJsonKey] !== 'undefined' && data[costPriceJsonKey] !== null) {
                                $baseCostDisplayElement.text(parseFloatSafely(data[costPriceJsonKey]).toFixed(2).replace('.', ','));
                            } else {
                                $baseCostDisplayElement.text('---');
                            }
                        }
                        updateItemTotal($row);
                    },
                    error: function(xhr, status, error) {
                        console.error('[APIUpdater] Error fetching data for URL', fetchUrl, 'Error:', error, 'Status:', status);
                        if ($priceInput.length) {
                            const currentManualPriceFlag = $priceInput.attr('data-manual-price');
                            const isManuallySet = currentManualPriceFlag === 'true';
                            if (!isManuallySet) {
                                $priceInput.val('0.00');
                            }
                        } else if ($priceReadonlyDisplay.length) {
                            $priceReadonlyDisplay.text('-');
                        }
                        if (stockJsonKey && $stockDisplayElement.length) $stockDisplayElement.text('Ошибка'); 
                        if (costPriceJsonKey && $baseCostDisplayElement.length) $baseCostDisplayElement.text('Ошибка');
                        updateItemTotal($row);
                    }
                });
            } else { 
                if ($priceInput.length) {
                    const currentManualPriceFlag = $priceInput.attr('data-manual-price');
                    const isManuallySet = currentManualPriceFlag === 'true';
                    if (isUserInteraction || !isManuallySet) { 
                        $priceInput.val('0.00');
                    }
                } else if ($priceReadonlyDisplay.length) {
                    $priceReadonlyDisplay.text('-');
                }
                if (stockJsonKey && $stockDisplayElement.length) $stockDisplayElement.text(''); 
                if (costPriceJsonKey && $baseCostDisplayElement.length) $baseCostDisplayElement.text('---');
                updateItemTotal($row);
            }
        }

        // ПОТОМ ОБРАБОТЧИКИ СОБЫТИЙ:
        $(document).on('change', '#product_items-group select[name$="-product"], #service_items-group select[name$="-service"]', function() {
            console.log(`[Event] 'change' on select: ${$(this).attr('name')}, Value: ${$(this).val()}`);
            
            if ($(this).attr('name').includes('-product')) {
                // Вызываем с isUserInteraction = true. stockDisplaySuffix будет по умолчанию " шт."
                fetchAndUpdatePriceAndStock(this, 'price_at_order', '/products-api/get-price/', 'retail_price', 'stock_quantity', 'cost_price', true); 
            } else if ($(this).attr('name').includes('-service')) {
                // Для услуг stockDisplaySuffix не используется, isUserInteraction = true
                fetchAndUpdatePriceAndStock(this, 'price_at_order', '/orders-api/get-service-price/', 'price', null, null, true); 
            }
        });
        
        $(document).on('input change', 
                       '#product_items-group input[name$="-quantity"], #service_items-group input[name$="-quantity"]', 
                       function() {
            const $row = $(this).closest('tr[class*="dynamic-"], .form-row[class*="dynamic-"]');
            updateItemTotal($row);
        });

        $(document).on('input', '#product_items-group input[name$="-price_at_order"], #service_items-group input[name$="-price_at_order"]', function() {
            const $this = $(this);
            if (!$this.is('[readonly]') && $this.is(':visible')) { 
                $this.attr('data-manual-price', 'true');
                console.log(`[Event] 'input' on price field: ${$this.attr('name')}. data-manual-price SET to true. New value: ${$this.val()}`);
                const $row = $this.closest('tr[class*="dynamic-"], .form-row[class*="dynamic-"]');
                updateItemTotal($row); 
            }
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
                updateItemTotal($row); 
            }
        });
        $(document).on('formset:removed', function(event, $row, formsetName) {
            updateOrderTotal();
            determineOrderTypeViaAPI();
        });

        // ПОТОМ ИНИЦИАЛИЗАЦИОННЫЙ КОД:
        // isUserInteraction = false (по умолчанию), stockDisplaySuffix = " шт." (по умолчанию)
        $('#product_items-group tr.dynamic-product_items:not(.empty-form), #product_items-group .dynamic-product_items.form-row:not(.empty-form)').each(function() {
            const $row = $(this);
            const $select = $row.find('select[name$="-product"]');
            if ($select.length && $select.val()) {
                fetchAndUpdatePriceAndStock($select[0], 'price_at_order', '/products-api/get-price/', 'retail_price', 'stock_quantity', 'cost_price');
            } else {
                updateItemTotal($row);
            }
        });
        $('#service_items-group tr.dynamic-service_items:not(.empty-form), #service_items-group .dynamic-service_items.form-row:not(.empty-form)').each(function() {
            const $row = $(this);
            const $select = $row.find('select[name$="-service"]');
            if ($select.length && $select.val()) {
                 fetchAndUpdatePriceAndStock($select[0], 'price_at_order', '/orders-api/get-service-price/', 'price', null, null);
            } else {
                updateItemTotal($row);
            }
        });
        
        setTimeout(function() {
            updateOrderTotal(); 
            determineOrderTypeViaAPI(); 
        }, 300);

        console.log('[PriceUpdater] Initialized.');
    } else {
        console.warn('[PriceUpdater] Django jQuery not available.');
    }
});