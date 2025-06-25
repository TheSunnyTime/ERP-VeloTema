// Система обновления остатков - новая версия
document.addEventListener('DOMContentLoaded', function() {
    console.log('[AvailableUpdater] Запуск новой системы обновления остатков');

    // Функция обновления остатков
    function updateStockDisplays() {
        console.log('[AvailableUpdater] Начинаем обновление остатков');
        
        // Ищем все поля с остатками
        const stockFields = document.querySelectorAll('.available-quantity-display');
        console.log('[AvailableUpdater] Найдено полей остатков:', stockFields.length);
        
        // Обновляем каждое поле
        stockFields.forEach((field, index) => {
            const productId = field.dataset.productId;
            const totalStock = parseInt(field.dataset.stockQuantity, 10) || 0;
            const reserved = parseInt(field.dataset.reservedExternally || "0", 10) || 0;
            const available = totalStock - reserved;
            
            console.log(`[AvailableUpdater] Поле ${index + 1} - Товар: ${productId}, Всего: ${totalStock}, Резерв: ${reserved}, Доступно: ${available}`);
            
            // Обновляем цифру на экране
            field.textContent = available;
        });
    }

    // Следим за изменениями в списке товаров (основной способ)
    document.addEventListener('change', function(event) {
        // Проверяем - это поле выбора товара?
        if (event.target.tagName === 'SELECT' && 
            event.target.name && 
            event.target.name.includes('product_items') && 
            event.target.name.includes('-product')) {
            
            console.log('[AvailableUpdater] 🎯 ТОВАР ВЫБРАН!');
            console.log('[AvailableUpdater] Имя поля:', event.target.name);
            console.log('[AvailableUpdater] Выбранный товар ID:', event.target.value);
            
            // Ждем 3 секунды чтобы данные успели загрузиться с сервера
            setTimeout(function() {
                console.log('[AvailableUpdater] Прошло 3 секунды - обновляем остатки');
                updateStockDisplays();
            }, 3000);
        }
    });

    // Следим за изменениями количества
    document.addEventListener('input', function(event) {
        if (event.target.name && event.target.name.includes('quantity')) {
            console.log('[AvailableUpdater] Изменено количество');
            updateStockDisplays();
        }
    });

    // Специально для выпадающих списков Select2
    document.addEventListener('select2:select', function(event) {
        console.log('[AvailableUpdater] 🎯 Select2 - товар выбран');
        
        setTimeout(function() {
            console.log('[AvailableUpdater] Select2 - обновляем остатки через 3 сек');
            updateStockDisplays();
        }, 3000);
    });

    // Обновляем остатки при загрузке страницы
    setTimeout(function() {
        console.log('[AvailableUpdater] Первоначальное обновление остатков');
        updateStockDisplays();
    }, 2000);

    console.log('[AvailableUpdater] ✅ Система готова');
});