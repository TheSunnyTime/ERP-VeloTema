// orders/static/orders/js/order_form_conditional_fields.js
if (window.django && window.django.jQuery) {
    (function($) {
        $(document).ready(function() {
            console.log('[ConditionalFields] Initializing conditional fields logic...');
            var orderTypeSelect = $('#id_order_type');
            var performerRow = $('.form-row.field-performer');
            var repairedItemRow = $('.form-row.field-repaired_item');
            var statusSelect = $('#id_status'); // <--- НОВОЕ: Получаем select статуса
            var isAddPage = window.location.pathname.includes('/add/');

            // --- Начальные проверки наличия элементов ---
            if (!orderTypeSelect.length && !$('div.form-row.field-order_type div.readonly').length) { // Проверяем и select и readonly
                console.warn('[ConditionalFields] Order Type select/readonly field not found.');
            }
            if (!performerRow.length) {
                console.warn('[ConditionalFields] Performer field row not found.');
            }
            if (!repairedItemRow.length) {
                console.warn('[ConditionalFields] Repaired Item field row not found.');
            }
            if (!statusSelect.length && !$('div.form-row.field-status div.readonly').length) { // Проверяем и select и readonly статуса
                console.warn('[ConditionalFields] Status select/readonly field not found.');
            }

            // --- КОНСТАНТА для значения статуса "Новый" ---
            // ВАЖНО: Это значение должно соответствовать Order.STATUS_NEW в Python
            // Если у вас статусы могут меняться, лучше передавать это значение из Python в шаблон,
            // например, через data-атрибут на каком-нибудь элементе.
            const STATUS_NEW_VALUE = 'new';

            function updateDynamicFields() { // Переименовал для ясности
                console.log('[ConditionalFields] updateDynamicFields CALLED. isAddPage:', isAddPage);

                let currentOrderTypeName = '';
                let orderTypeSuccessfullyDetermined = false;
                let currentStatusValue = ''; // <--- НОВОЕ: для значения статуса

                // 1. Определяем текущий тип заказа
                if (orderTypeSelect.length && orderTypeSelect.is('select') && !orderTypeSelect.is('[readonly]') && !orderTypeSelect.is(':disabled')) {
                    const selectedOrderTypeId = orderTypeSelect.val();
                    if (selectedOrderTypeId) {
                        currentOrderTypeName = orderTypeSelect.find('option:selected').text().trim().toLowerCase();
                        orderTypeSuccessfullyDetermined = true;
                    }
                } else {
                    const $readonlyDiv = $('div.form-row.field-order_type div.readonly');
                    if ($readonlyDiv.length) {
                        currentOrderTypeName = $readonlyDiv.text().trim().toLowerCase();
                        orderTypeSuccessfullyDetermined = true;
                    }
                }
                console.log('[ConditionalFields] Current Order Type Name:', currentOrderTypeName);

                // 1.1. Определяем текущий статус заказа <--- НОВОЕ
                if (statusSelect.length && statusSelect.is('select') && !statusSelect.is('[readonly]') && !statusSelect.is(':disabled')) {
                    currentStatusValue = statusSelect.val();
                } else {
                    const $readonlyStatusDiv = $('div.form-row.field-status div.readonly');
                    if ($readonlyStatusDiv.length) {
                        // Для readonly статуса нам нужно получить его ключ, а не отображаемое имя.
                        // Это сложнее без доп. информации на странице.
                        // Пока предполагаем, что если статус readonly, то он не "Новый" для целей обязательности исполнителя,
                        // или что серверная валидация справится.
                        // Для более точного JS, нужно было бы передавать ключ статуса.
                        // Сейчас просто проверим, что он не пустой.
                        // Если у вас есть способ получить КЛЮЧ статуса из readonly, используйте его.
                        // Например, если бы у вас был data-status-key атрибут.
                        // Пока упрощенно: если статус readonly, считаем, что он не "Новый" (для JS логики).
                        // Это НЕ ИДЕАЛЬНО, но для JS может быть достаточно, если серверная валидация надежна.
                        // Лучше всего, если статус не редактируется, его значение уже не "Новый".
                        // В твоем get_readonly_fields статус становится readonly, если он 'issued'.
                        // Если он 'new' и readonly (что маловероятно), эта логика может дать сбой.
                        // Давай пока оставим так: если статус readonly, то JS не будет считать его "Новым"
                        // для целей снятия обязательности с исполнителя.
                        const statusText = $readonlyStatusDiv.text().trim();
                        if (statusText) { // Если есть текст
                             // Это очень грубое предположение, что если он readonly и не пустой, то это не "Новый"
                             // для целей JS. Серверная валидация должна быть основной.
                            currentStatusValue = statusText.toLowerCase() !== 'новый' ? 'not_new_placeholder' : STATUS_NEW_VALUE;
                        }
                        console.log('[ConditionalFields] Readonly Status Text:', statusText, 'Assumed JS Status Value:', currentStatusValue);
                    }
                }
                console.log('[ConditionalFields] Current Status Value:', currentStatusValue);


                // 2. Проверяем, является ли тип заказа "Ремонтом"
                var isRepairType = false;
                if (orderTypeSuccessfullyDetermined && currentOrderTypeName === 'ремонт') {
                    isRepairType = true;
                }
                console.log('[ConditionalFields] isRepairType =', isRepairType);

                // 3. Управляем видимостью и обязательностью поля "Исполнитель"
                var performerField = $('#id_performer'); // Само поле select
                var performerLabel = $('label[for="id_performer"]'); // Метка поля

                if (performerRow.length) {
                    if (isAddPage) {
                        performerRow.hide();
                        if (performerField.length) performerField.removeAttr('required');
                        if (performerLabel.length) {
                            performerLabel.removeClass('required');
                            performerLabel.find('span.required-marker').remove();
                        }
                        console.log('[ConditionalFields] ADD PAGE: HIDING performer field.');
                    } else if (isRepairType) {
                        performerRow.show();
                        console.log('[ConditionalFields] SHOWING performer field (Repair type on Edit page).');
                        // Теперь проверяем статус
                        if (currentStatusValue && currentStatusValue !== STATUS_NEW_VALUE) {
                            console.log('[ConditionalFields] Performer IS REQUIRED (Repair, Status NOT New).');
                            if (performerField.length) performerField.attr('required', 'required');
                            if (performerLabel.length && !performerLabel.find('span.required-marker').length) {
                                performerLabel.addClass('required').append('<span class="required-marker" style="color:red; margin-left: 2px;">*</span>');
                            }
                        } else {
                            console.log('[ConditionalFields] Performer IS NOT REQUIRED (Repair, Status IS New or empty/unknown).');
                            if (performerField.length) performerField.removeAttr('required');
                            if (performerLabel.length) {
                                performerLabel.removeClass('required');
                                performerLabel.find('span.required-marker').remove();
                            }
                        }
                    } else { // Не "Ремонт" и не страница добавления
                        performerRow.hide();
                        if (performerField.length) performerField.removeAttr('required');
                        if (performerLabel.length) {
                            performerLabel.removeClass('required');
                            performerLabel.find('span.required-marker').remove();
                        }
                        console.log('[ConditionalFields] HIDING performer field (Not Repair type).');
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

            // Первоначальный вызов
            updateDynamicFields();

            // Обработчик для кастомного события
            $(document).on('order_type_dynamically_updated', function() {
                console.log('[ConditionalFields] Custom event "order_type_dynamically_updated" RECEIVED.');
                updateDynamicFields();
            });

            // Обработчик изменения "Тип заказа"
            if (orderTypeSelect.length && orderTypeSelect.is('select') && !orderTypeSelect.is('[readonly]') && !orderTypeSelect.is(':disabled')) {
                orderTypeSelect.on('change select2:select select2:unselect', function() {
                    console.log('[ConditionalFields] Event on #id_order_type select triggered.');
                    setTimeout(updateDynamicFields, 70);
                });
            }

            // <--- НОВЫЙ ОБРАБОТЧИК для изменения "Статус" ---
            if (statusSelect.length && statusSelect.is('select') && !statusSelect.is('[readonly]') && !statusSelect.is(':disabled')) {
                statusSelect.on('change select2:select select2:unselect', function() {
                    console.log('[ConditionalFields] Event on #id_status select triggered.');
                    setTimeout(updateDynamicFields, 70); // Вызываем ту же функцию
                });
            }
        });
    })(django.jQuery);
} else {
    console.error("[ConditionalFields] django.jQuery is not available.");
}