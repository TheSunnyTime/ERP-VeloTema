// F:\CRM 2.0\ERP\cash_register\static\cash_register\js\transaction_form.js
document.addEventListener('DOMContentLoaded', function() {
    console.log("[CashTransactionForm] DOMContentLoaded event fired.");

    if (typeof django !== 'undefined' && typeof django.jQuery !== 'undefined') {
        const $ = django.jQuery; 

        // Пытаемся найти основной элемент формы - выпадающий список типа транзакции
        const transactionTypeSelect = $('#id_transaction_type');

        // Продолжаем работу только если этот элемент найден (т.е. мы на странице добавления/редактирования)
        if (transactionTypeSelect.length > 0) {
            console.log("[CashTransactionForm] django.jQuery found AND on add/change form. Initializing script logic.");

            const expenseCategoryRow = $('.field-expense_category'); 
            const orderRow = $('.field-order'); 

            function toggleFieldsBasedOnType() {
                const currentType = transactionTypeSelect.val();
                console.log("[CashTransactionForm] Transaction type changed/set to:", currentType);

                if (currentType === 'expense') {
                    expenseCategoryRow.show();
                    if (orderRow.length) { orderRow.hide(); }
                    console.log("[CashTransactionForm] Type: Expense. Showing Expense Category, Hiding Order.");
                } else if (currentType === 'income'){
                    expenseCategoryRow.hide();
                    const expenseCategorySelect = expenseCategoryRow.find('select, input');
                    if (expenseCategorySelect.val()) {
                        expenseCategorySelect.val(''); 
                        if (expenseCategorySelect.data('select2')) { // Если используется Select2
                            expenseCategorySelect.trigger('change.select2'); 
                        }
                        console.log("[CashTransactionForm] Cleared Expense Category for Income type.");
                    }
                    if (orderRow.length) { orderRow.show(); }
                    console.log("[CashTransactionForm] Type: Income. Hiding Expense Category, Showing Order (if present).");
                } else { 
                    expenseCategoryRow.hide();
                    if (orderRow.length) { orderRow.show(); }
                    console.log("[CashTransactionForm] Type: None or Other. Hiding Expense Category, Showing Order (if present).");
                }
            }

            // Первоначальный вызов и установка обработчика
            toggleFieldsBasedOnType(); 
            transactionTypeSelect.on('change', toggleFieldsBasedOnType);
            console.log("[CashTransactionForm] Initial field visibility set and change handler attached.");

        } else {
            // Это сообщение теперь будет появляться на страницах, где нет формы (например, список транзакций)
            console.log("[CashTransactionForm] Transaction type select ('#id_transaction_type') not found. Assuming not on add/change form. No handlers attached.");
        }

    } else {
        console.error("[CashTransactionForm] CRITICAL: django.jQuery not found on DOMContentLoaded! Admin media not loading correctly or custom JS is loaded too early.");
    }
});