// orders/static/orders/js/order_form_conditional_fields.js
if (window.django && window.django.jQuery) {
    (function($) {
        $(document).ready(function() {
            console.log('[ConditionalFields] Initializing conditional fields logic...');
            var orderTypeSelect = $('#id_order_type');
            var performerRow = $('.form-row.field-performer');
            var repairedItemRow = $('.form-row.field-repaired_item'); // Находим строку для поля "Изделие"
            var isAddPage = window.location.pathname.includes('/add/');

            if (!orderTypeSelect.length) {
                console.warn('[ConditionalFields] Order Type select field (#id_order_type) not found. Conditional logic might not work.');
                // Не выходим, так как может быть readonly поле
            }
            if (!performerRow.length) {
                console.warn('[ConditionalFields] Performer field row (.form-row.field-performer) not found on this page.');
            }
            if (!repairedItemRow.length) {
                console.warn('[ConditionalFields] Repaired Item field row (.form-row.field-repaired_item) not found on this page.');
            }

            function updateRepairOrderFields() {
                console.log('[ConditionalFields] updateRepairOrderFields CALLED. isAddPage:', isAddPage);

                let currentOrderTypeName = '';
                let orderTypeSuccessfullyDetermined = false;

                // 1. Определяем текущий тип заказа
                if (orderTypeSelect.length && orderTypeSelect.is('select') && !orderTypeSelect.is('[readonly]') && !orderTypeSelect.is(':disabled')) {
                    const selectedOrderTypeId = orderTypeSelect.val();
                    if (selectedOrderTypeId) {
                        currentOrderTypeName = orderTypeSelect.find('option:selected').text().trim().toLowerCase();
                        orderTypeSuccessfullyDetermined = true;
                    }
                    console.log('[ConditionalFields] Found EDITABLE <select #id_order_type>. Value ID:', selectedOrderTypeId, 'Selected Text:', currentOrderTypeName);
                } else {
                    const $readonlyDiv = $('div.form-row.field-order_type div.readonly');
                    if ($readonlyDiv.length) {
                        currentOrderTypeName = $readonlyDiv.text().trim().toLowerCase();
                        orderTypeSuccessfullyDetermined = true;
                        console.log('[ConditionalFields] Found READONLY div.field-order_type. Text content:', currentOrderTypeName);
                    } else {
                        console.warn('[ConditionalFields] Neither editable <select #id_order_type> nor readonly div.field-order_type found for order type.');
                    }
                }

                // 2. Проверяем, является ли тип заказа "Ремонтом"
                var isRepairType = false;
                if (orderTypeSuccessfullyDetermined && currentOrderTypeName === 'ремонт') { // Сравниваем с "ремонт" в нижнем регистре
                    isRepairType = true;
                }
                console.log('[ConditionalFields] Based on order type ("' + currentOrderTypeName + '"), determined isRepairType =', isRepairType);

                // 3. Управляем видимостью поля "Исполнитель"
                if (performerRow.length) {
                    if (isAddPage) { // На странице добавления "Исполнитель" всегда скрыт (согласно твоей предыдущей логике)
                        performerRow.hide();
                        console.log('[ConditionalFields] ADD PAGE: HIDING performer field unconditionally.');
                    } else if (isRepairType) {
                        performerRow.show();
                        console.log('[ConditionalFields] SHOWING performer field (Repair type on Edit page).');
                    } else {
                        performerRow.hide();
                        console.log('[ConditionalFields] HIDING performer field (Not Repair type or Edit page).');
                    }
                }

                // 4. Управляем видимостью поля "Изделие"
                if (repairedItemRow.length) {
                    if (isRepairType) {
                        repairedItemRow.show();
                        console.log('[ConditionalFields] SHOWING repaired_item field.');
                    } else {
                        repairedItemRow.hide();
                        console.log('[ConditionalFields] HIDING repaired_item field.');
                    }
                }
            }

            // Первоначальный вызов функции для установки правильного состояния полей при загрузке страницы
            updateRepairOrderFields();

            // Обработчик для кастомного события (если тип заказа меняется другим скриптом)
            $(document).on('order_type_dynamically_updated', function() {
                console.log('[ConditionalFields] Custom event "order_type_dynamically_updated" RECEIVED.');
                updateRepairOrderFields();
            });

            // Обработчик изменения значения в выпадающем списке "Тип заказа"
            if (orderTypeSelect.length && orderTypeSelect.is('select') && !orderTypeSelect.is('[readonly]') && !orderTypeSelect.is(':disabled')) {
                orderTypeSelect.on('change select2:select select2:unselect', function() {
                    console.log('[ConditionalFields] Event on #id_order_type select triggered by user/select2.');
                    // Небольшая задержка может быть полезна, если другие скрипты тоже реагируют на это событие
                    // или если значение в selected text не сразу обновляется.
                    setTimeout(updateRepairOrderFields, 70); 
                });
            }
        });
    })(django.jQuery);
} else {
    console.error("[ConditionalFields] django.jQuery is not available. This script depends on it.");
}