// F:\CRM 2.0\ERP\orders\static\orders\js\order_form_price_updater.js

document.addEventListener('DOMContentLoaded', function() {

var orderStatusMarker = document.getElementById('order-status-marker');
var orderStatus = orderStatusMarker ? orderStatusMarker.value : null;
var disabledStatuses = ['issued', 'cancelled']; // ключи такие же, как в Order.STATUS_ISSUED и Order.STATUS_CANCELLED

if (orderStatus && disabledStatuses.indexOf(orderStatus) !== -1) {
    console.log('[OrderJS] Динамика отключена для статуса: ' + orderStatus);
    return;
}

    if (typeof django !== 'undefined' && typeof django.jQuery !== 'undefined') {
        const $ = django.jQuery;
        console.log('[PriceUpdater] Initializing...');
        let pageFullyInitialized = false;

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
                return;
            }

            if (!$orderTypeSelect.length && !$orderTypeReadonlyDiv.length) {
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
                    if (response.order_type_id !== null && typeof response.order_type_name !== 'undefined') {
                        let successfullyUpdatedDisplay = false;
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
                                    typeActuallyChanged = true;
                                }
                                successfullyUpdatedDisplay = true;
                            }
                        }

                        if (!successfullyUpdatedDisplay && $orderTypeReadonlyDiv.length) {
                            const currentTextInReadonly = $orderTypeReadonlyDiv.find('a').length ? $orderTypeReadonlyDiv.find('a').text().trim() : $orderTypeReadonlyDiv.text().trim();
                            if (currentTextInReadonly.toLowerCase() !== response.order_type_name.trim().toLowerCase()) {
                                const $linkInsideReadonly = $orderTypeReadonlyDiv.find('a');
                                if ($linkInsideReadonly.length) {
                                    $linkInsideReadonly.text(response.order_type_name);
                                } else {
                                    $orderTypeReadonlyDiv.text(response.order_type_name);
                                }
                                typeActuallyChanged = true;
                            }
                        }

                        if (typeActuallyChanged) {
                            $(document).trigger('order_type_dynamically_updated');
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

        // Функция обновления цены и стока с учетом флага ручного изменения
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

            // --- ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ: УБИРАЕМ ЛИШНЕЕ УСЛОВИЕ ---
            // Теперь проверка работает всегда: и при загрузке страницы, и при действиях пользователя.
            // Если в поле цены УЖЕ ЕСТЬ ЧИСЛО БОЛЬШЕ НУЛЯ, НИЧЕГО НЕ ДЕЛАЕМ.
            if ($priceInput.length && parseFloatSafely($priceInput.val()) > 0) {
                // Мы добавляем проверку, чтобы лог был понятнее
                if (isUserInteraction) {
                    console.log(`[Price Updater] Обнаружена ручная цена (${$priceInput.val()}). Обновление отменено.`);
                } else {
                    console.log(`[Price Updater] При загрузке страницы обнаружена сохраненная цена (${$priceInput.val()}). Оставляем ее без изменений.`);
                }
                return; // Выходим и сохраняем ручную/сохраненную цену.
            }
            // --- КОНЕЦ ИСПРАВЛЕНИЯ ---

            // Если мы дошли сюда, значит поле цены пустое или 0. Можно безопасно обновлять.
            
            // Находим остальные элементы для обновления
            let $stockDisplayElement = $();
            if (stockJsonKey) { $stockDisplayElement = $row.find(`td.field-get_current_stock p, div.field-get_current_stock div.readonly`); }
            const $baseCostDisplayElement = $row.find(`td.field-display_product_base_cost_price p, div.field-display_product_base_cost_price div.readonly`);
            const $priceReadonlyDisplay = $row.find(`td.field-${priceFieldIdentifierInModel} p`);
            
            if (selectedId) {
                const fetchUrl = `${apiUrlPrefix}${selectedId}/`;
                $.ajax({
                    url: fetchUrl,
                    type: 'GET',
                    success: function(data) {
                        // Логика стала проще: мы здесь, только если цена 0. Просто обновляем все поля.
                        if ($priceInput.length && !$priceInput.is('[readonly]') && !$priceInput.is(':disabled')) {
                            if (data && typeof data[priceJsonKey] !== 'undefined' && data[priceJsonKey] !== null) {
                                const priceToSet = parseFloatSafely(data[priceJsonKey]).toFixed(2);
                                $priceInput.val(priceToSet);
                            } else {
                                $priceInput.val('0.00');
                            }
                        } else if ($priceReadonlyDisplay.length) {
                            if (data && typeof data[priceJsonKey] !== 'undefined' && data[priceJsonKey] !== null) {
                                const priceToSetForDisplay = parseFloatSafely(data[priceJsonKey]).toFixed(2).replace('.', ',');
                                $priceReadonlyDisplay.text(priceToSetForDisplay);
                            } else {
                                $priceReadonlyDisplay.text('-');
                            }
                        }
                        
                        if (stockJsonKey && $stockDisplayElement.length) { 
                            if (typeof data[stockJsonKey] !== 'undefined' && data[stockJsonKey] !== null) {
                                let stockFromApi = parseInt(data[stockJsonKey], 10);
                                let textToDisplay = isNaN(stockFromApi) ? 'N/A' : String(stockFromApi) + stockDisplaySuffix;
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
                        console.error(`[APIUpdater] Ошибка загрузки данных для ${fetchUrl}: ${error}`);
                        if ($priceInput.length) { $priceInput.val('0.00'); }
                        if ($priceReadonlyDisplay.length) { $priceReadonlyDisplay.text('-'); }
                        if (stockJsonKey && $stockDisplayElement.length) $stockDisplayElement.text('Ошибка'); 
                        if (costPriceJsonKey && $baseCostDisplayElement.length) $baseCostDisplayElement.text('Ошибка');
                        updateItemTotal($row);
                    }
                });
            } else { 
                // Если товар сбросили (выбрали "---"), обнуляем цену и прочие поля
                if ($priceInput.length) { $priceInput.val('0.00'); }
                if ($priceReadonlyDisplay.length) { $priceReadonlyDisplay.text('-'); }
                if (stockJsonKey && $stockDisplayElement.length) $stockDisplayElement.text(''); 
                if (costPriceJsonKey && $baseCostDisplayElement.length) $baseCostDisplayElement.text('---');
                updateItemTotal($row);
            }
        }

        // При выборе товара пользователем: считаем это ручным действием (isUserInteraction = true только после полной инициализации)
        $(document).on('change', '#product_items-group select[name$="-product"], #service_items-group select[name$="-service"]', function() {
            // Старая строка: const considerAsUserInteraction = pageFullyInitialized;
            // Новая логика: Если сработал этот обработчик, это ВСЕГДА действие пользователя.
            const considerAsUserInteraction = true;
            
            console.log('[PriceUpdater] 🔍 ТОВАР ВЫБРАН! Считаем это действием пользователя (isUserInteraction = true).');
            
            if ($(this).attr('name').includes('-product')) {
                fetchAndUpdatePriceAndStock(this, 'price_at_order', '/products-api/get-price/', 'retail_price', 'stock_quantity', 'cost_price', considerAsUserInteraction);
            } else if ($(this).attr('name').includes('-service')) {
                fetchAndUpdatePriceAndStock(this, 'price_at_order', '/orders-api/get-service-price/', 'price', null, null, considerAsUserInteraction);
            }
        });
        
        $(document).on('input change', '#product_items-group input[name$="-quantity"], #service_items-group input[name$="-quantity"]', function() {
            const $row = $(this).closest('tr[class*="dynamic-"], .form-row[class*="dynamic-"]'); updateItemTotal($row);
        });

        // Здесь мы всегда ставим ручной флаг, когда пользователь меняет цену
        $(document).on('input', '#product_items-group input[name$="-price_at_order"], #service_items-group input[name$="-price_at_order"]', function() {
            const $this = $(this);
            if (!$this.is('[readonly]') && $this.is(':visible')) { 
                $this.attr('data-manual-price', 'true');
                const $row = $this.closest('tr[class*="dynamic-"], .form-row[class*="dynamic-"]');
                updateItemTotal($row); 
            }
        });

        $(document).on('formset:added', function(event, $rowFromArgs, formsetName) {
            let $row = $($rowFromArgs); 
            if (!($row && $row.length && typeof $row.find === 'function')) {
                const $lastRowInFormset = $('#' + formsetName + '-group .dynamic-' + formsetName + ':not(.empty-form)').last();
                if ($lastRowInFormset.length) { $row = $lastRowInFormset; } 
                else { updateOrderTotal(); determineOrderTypeViaAPI(); return; }
            }
            if ($row.length && typeof $row.find === 'function') { 
                const $selectsInRow = $row.find('select.admin-autocomplete'); 
                if ($selectsInRow.length && typeof $selectsInRow.select2 === 'function') {
                     $selectsInRow.each(function() {
                        const $select = $(this); if (!$select.data('select2')) { $select.select2(); }
                     });
                }
                updateItemTotal($row); 
            }
        });
        $(document).on('formset:removed', function(event, $row, formsetName) {
            updateOrderTotal(); determineOrderTypeViaAPI();
        });

        // Автоматическая инициализация (при загрузке страницы и добавлении новых строк): всегда isUserInteraction = false!
        $('#product_items-group tr.dynamic-product_items:not(.empty-form), #product_items-group .dynamic-product_items.form-row:not(.empty-form)').each(function() {
            const $row = $(this); const $select = $row.find('select[name$="-product"]');
            if ($select.length && $select.val()) {
                fetchAndUpdatePriceAndStock($select[0], 'price_at_order', '/products-api/get-price/', 'retail_price', 'stock_quantity', 'cost_price', false);
            } else {
                updateItemTotal($row);
            }
        });
        $('#service_items-group tr.dynamic-service_items:not(.empty-form), #service_items-group .dynamic-service_items.form-row:not(.empty-form)').each(function() {
            const $row = $(this); const $select = $row.find('select[name$="-service"]');
            if ($select.length && $select.val()) {
                fetchAndUpdatePriceAndStock($select[0], 'price_at_order', '/orders-api/get-service-price/', 'price', null, null, false);
            } else {
                updateItemTotal($row);
            }
        });
        
        setTimeout(function() {
            updateOrderTotal(); determineOrderTypeViaAPI(); 
            pageFullyInitialized = true; 
            console.log('[PriceUpdater] Page fully initialized.');
        }, 100); 

        console.log('[PriceUpdater] Initialized event handlers and started initial processing.');
    } else { console.warn('[PriceUpdater] Django jQuery not available.'); }
});