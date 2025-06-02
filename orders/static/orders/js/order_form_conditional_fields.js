// orders/static/orders/js/order_form_conditional_fields.js
if (window.django && window.django.jQuery) {
    (function($) {
        $(document).ready(function() {
            console.log('[ConditionalFields] Initializing for "Исполнитель" field...'); 
            var orderTypeSelect = $('#id_order_type'); 
            var performerRow = $('.form-row.field-performer');
            var isAddPage = window.location.pathname.includes('/add/');

            if (!performerRow.length) {
                console.warn('[ConditionalFields] Performer field row (.form-row.field-performer) not found on this page. Exiting.');
                return; 
            }

            function togglePerformerField() {
                console.log('[ConditionalFields] togglePerformerField CALLED. isAddPage:', isAddPage);

                if (isAddPage) { 
                    performerRow.hide();
                    console.log('[ConditionalFields] ADD PAGE DETECTED: Hiding performer field.');
                    return; 
                }

                let currentOrderTypeName = '';
                let orderTypeSuccessfullyDetermined = false;

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

                var showPerformer = false;
                if (orderTypeSuccessfullyDetermined && currentOrderTypeName === 'ремонт') { 
                    showPerformer = true;
                }

                console.log('[ConditionalFields] Based on order type ("' + currentOrderTypeName + '"), determined showPerformer =', showPerformer);

                if (showPerformer) {
                    performerRow.show();
                    console.log('[ConditionalFields] SHOWING performer field.');
                } else {
                    performerRow.hide();
                    console.log('[ConditionalFields] HIDING performer field.');
                }
            }

            togglePerformerField(); 

            $(document).on('order_type_dynamically_updated', function() {
                console.log('[ConditionalFields] Custom event "order_type_dynamically_updated" RECEIVED.');
                togglePerformerField(); 
            });

            if (orderTypeSelect.length && orderTypeSelect.is('select') && !orderTypeSelect.is('[readonly]') && !orderTypeSelect.is(':disabled')) {
                orderTypeSelect.on('change select2:select select2:unselect', function() {
                    console.log('[ConditionalFields] Event on #id_order_type select triggered by user/select2.');
                    setTimeout(togglePerformerField, 70); 
                });
            }
        });
    })(django.jQuery);
} else {
    console.error("[ConditionalFields] django.jQuery is not available. This script depends on it.");
}