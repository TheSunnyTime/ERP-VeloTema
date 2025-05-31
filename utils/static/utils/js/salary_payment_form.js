// F:\CRM 2.0\ERP\utils\static\utils\js\salary_payment_form.js
(function($) {
    $(document).ready(function() {
        console.log('[SalaryPaymentFormJS] Initializing...');

        const employeeSelect = $('#id_employee'); // ID поля выбора сотрудника
        
        // Место для отображения баланса. Мы будем обновлять содержимое 
        // элемента, который генерируется методом display_current_employee_balance.
        // Django admin для readonly полей-методов часто создает <div class="readonly">...</div>
        // внутри field-ИМЯ_МЕТОДА. Нам нужен более точный селектор или ID.
        // Пока что, найдем родительский div для нашего поля и будем вставлять текст туда.
        // Предположим, что display_current_employee_balance генерирует что-то внутри div.field-display_current_employee_balance
        const balanceDisplayContainer = $('div.field-display_current_employee_balance div.readonly'); 
        // Если display_current_employee_balance возвращает просто текст, то у него может не быть вложенного div.readonly
        // Тогда нужно найти просто div.field-display_current_employee_balance > div (если там есть div от Django) или p
        
        if (!employeeSelect.length) {
            console.warn('[SalaryPaymentFormJS] Employee select field (#id_employee) not found.');
            return;
        }
        if (!balanceDisplayContainer.length) {
            console.warn('[SalaryPaymentFormJS] Balance display container (div.field-display_current_employee_balance div.readonly) not found. Dynamic balance will not work.');
            // Попробуем найти просто контейнер поля, если div.readonly нет
            // const fallbackBalanceContainer = $('div.field-display_current_employee_balance');
            // if (fallbackBalanceContainer.length) {
            //     console.log('[SalaryPaymentFormJS] Found fallback container div.field-display_current_employee_balance');
            //     // Здесь можно будет что-то делать с fallbackBalanceContainer
            // }
        } else {
             console.log('[SalaryPaymentFormJS] Balance display container found.');
        }


        function updateBalanceDisplay(employeeId) {
            if (!balanceDisplayContainer.length) {
                // Если контейнер не найден, ничего не делаем, но это уже залогировано выше
                return;
            }

            if (employeeId) {
                // URL к нашему API (убедись, что пространство имен 'utils' правильное)
                const apiUrl = `/admin/service-tools/api/get-employee-balance/${employeeId}/`;
                // Если utils включен в главный urls.py с префиксом (например, 'service-tools/'),
                // то URL будет /service-tools/api/get-employee-balance/${employeeId}/
                // или используй {% url 'utils:api_get_employee_balance' employee_id=0 %} в шаблоне для получения базового URL,
                // а потом заменяй 0 на реальный ID. Но для JS проще жестко задать, если структура URL стабильна.

                console.log('[SalaryPaymentFormJS] Fetching balance from:', apiUrl);
                balanceDisplayContainer.html('<em>Загрузка баланса...</em>'); // Показываем индикатор загрузки

                $.ajax({
                    url: apiUrl,
                    type: 'GET',
                    success: function(data) {
                        console.log('[SalaryPaymentFormJS] Balance data received:', data);
                        if (data && typeof data.current_balance !== 'undefined') {
                            balanceDisplayContainer.html(`<strong style="color: var(--body-fg);">${data.current_balance} руб.</strong> (Начислено: ${data.total_accrued}, Выплачено: ${data.total_paid})`);
                        } else if (data && data.error) {
                            balanceDisplayContainer.text(`Ошибка: ${data.error}`);
                        } else {
                            balanceDisplayContainer.text('Не удалось загрузить баланс.');
                        }
                    },
                    error: function(xhr, status, error) {
                        console.error('[SalaryPaymentFormJS] Error fetching balance:', error);
                        balanceDisplayContainer.text('Ошибка загрузки баланса.');
                    }
                });
            } else {
                // Если сотрудник не выбран, очищаем поле или ставим сообщение по умолчанию
                const defaultMessage = "Баланс будет рассчитан после выбора сотрудника.";
                balanceDisplayContainer.text(defaultMessage);
            }
        }

        // Событие изменения для Select2 (стандартный виджет Django для autocomplete_fields)
        employeeSelect.on('select2:select', function (e) {
            const selectedEmployeeId = $(this).val();
            console.log('[SalaryPaymentFormJS] Employee selected (select2:select):', selectedEmployeeId);
            updateBalanceDisplay(selectedEmployeeId);
        });
        
        employeeSelect.on('select2:clear', function (e) {
            console.log('[SalaryPaymentFormJS] Employee selection cleared (select2:clear).');
            updateBalanceDisplay(null); // Очищаем баланс
        });


        // Попытка обновить баланс при первоначальной загрузке страницы, если сотрудник уже выбран
        // (например, при редактировании или если форма открыта с ошибкой и поле employee заполнено)
        const initialEmployeeId = employeeSelect.val();
        if (initialEmployeeId) {
            console.log('[SalaryPaymentFormJS] Initial employee ID on page load:', initialEmployeeId);
            updateBalanceDisplay(initialEmployeeId);
        } else {
             if (balanceDisplayContainer.length) { // Устанавливаем сообщение по умолчанию, если контейнер есть
                balanceDisplayContainer.text("Выберите сотрудника для отображения баланса.");
             }
        }
    });
})(django.jQuery);