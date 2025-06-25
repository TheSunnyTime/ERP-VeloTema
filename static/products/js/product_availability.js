// Код для подсветки товаров без наличия в поиске
$(document).ready(function() {
    // Функция для добавления цвета к результатам поиска
    function colorizeSearchResults() {
        // Немного ждем, чтобы элементы Select2 загрузились
        setTimeout(function() {
            // Находим все элементы результатов поиска
            $('.select2-results__option').each(function() {
                // Получаем текст элемента
                var itemText = $(this).text();
                
                // Проверяем, содержит ли текст информацию о доступности
                // Ищем "Доступно сейчас: 0" или "Доступно: 0"
                if (itemText.includes('Доступно сейчас: 0') || 
                    itemText.includes('Доступно: 0') ||
                    itemText.match(/Доступно.*?: 0\D/)) {
                    
                    // Добавляем класс для товаров без наличия
                    $(this).addClass('product-not-available');
                }
            });
        }, 100);
    }
    
    // Запускаем функцию при открытии выпадающего списка
    $(document).on('select2:open', function() {
        colorizeSearchResults();
    });
    
    // И при каждой загрузке результатов поиска
    $(document).on('select2:results', function() {
        colorizeSearchResults();
    });
    
    // И при вводе текста в поле поиска
    $(document).on('keyup', '.select2-search__field', function() {
        colorizeSearchResults();
    });
});