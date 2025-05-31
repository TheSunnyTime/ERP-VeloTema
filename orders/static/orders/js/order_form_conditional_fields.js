// orders/static/orders/js/order_form_conditional_fields.js
if (window.django && window.django.jQuery) {
    (function($) {
        $(document).ready(function() {
            var orderTypeSelect = $('#id_order_type');
            var performerRow = $('.form-row.field-performer'); // Стандартный класс Django для строки поля
            
            // Проверяем, это страница добавления нового заказа или редактирования существующего
            // URL для добавления обычно заканчивается на /add/
            var isAddPage = window.location.pathname.includes('/add/'); // Проверяем наличие /add/ в пути

            if (!orderTypeSelect.length) {
                // console.warn('Conditional fields: order_type select not found.');
                if (isAddPage && performerRow.length) { // Если это страница добавления, скрыть исполнителя
                    performerRow.hide();
                }
                return; 
            }
            if (!performerRow.length) {
                // console.warn('Conditional fields: performer field row not found.');
                return;
            }

            function togglePerformerField() {
                // --- НОВАЯ ЛОГИКА для isAddPage ---
                if (isAddPage) { 
                    performerRow.hide(); // На странице создания нового заказа всегда скрываем поле "Исполнитель"
                    return; // Выходим, дальнейшая логика для новых заказов не нужна
                }
                // --- КОНЕЦ НОВОЙ ЛОГИКИ ---

                // Логика для страницы редактирования существующего заказа
                var selectedOrderTypeId = orderTypeSelect.val();
                var showPerformer = false;

                if (selectedOrderTypeId) {
                    var selectedOptionText = orderTypeSelect.find('option[value="' + selectedOrderTypeId + '"]').text();
                    if (selectedOptionText && selectedOptionText.trim().toLowerCase() === 'ремонт') {
                        showPerformer = true;
                    }
                }
                
                if (showPerformer) {
                    performerRow.show();
                } else {
                    performerRow.hide();
                    // Опционально: $('#id_performer').val('').trigger('change'); 
                }
            }

            // Первоначальное состояние при загрузке страницы
            togglePerformerField();

            // Обработчик изменения типа заказа
            orderTypeSelect.on('change', function() {
                togglePerformerField();
            });

            // Для select2
            if (orderTypeSelect.data('select2')) {
                 orderTypeSelect.on('select2:select select2:unselect', function (e) {
                    setTimeout(togglePerformerField, 50); 
                });
            }
        });
    })(django.jQuery);
} else {
    console.error("django.jQuery is not available. Conditional fields script will not run.");
}