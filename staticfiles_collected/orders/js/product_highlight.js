// Подсветка товаров без остатка красным цветом
document.addEventListener('DOMContentLoaded', function() {
    
    // Проверяем что мы на странице заказа
    var isOrderPage = window.location.pathname.includes('/order/') && 
                     (window.location.pathname.includes('/change/') || 
                      window.location.pathname.includes('/add/'));
    
    if (!isOrderPage) {
        console.log('[Подсветка] Не на странице заказа');
        return;
    }
    
    console.log('[Подсветка] Работаем на странице заказа');

    // Добавляем красные стили для товаров без остатка
    function addStyles() {
        if (!document.getElementById('highlight-styles')) {
            var style = document.createElement('style');
            style.id = 'highlight-styles';
            style.innerHTML = `
                li.select2-results__option.no-stock {
                    background-color: #FFE6E6 !important;
                    color: #CC0000 !important;
                    border-left: 4px solid #FF0000 !important;
                }
                li.select2-results__option--highlighted.no-stock {
                    background-color: #FFCCCC !important;
                    color: #990000 !important;
                    border-left: 4px solid #FF0000 !important;
                }
                .select2-results__option.no-stock {
                    background-color: #FFE6E6 !important;
                    color: #CC0000 !important;
                    border-left: 4px solid #FF0000 !important;
                }
                .select2-results__option--highlighted.no-stock {
                    background-color: #FFCCCC !important;
                    color: #990000 !important;
                    border-left: 4px solid #FF0000 !important;
                }
            `;
            document.head.appendChild(style);
            console.log('[Подсветка] Стили добавлены');
        }
    }

    // Функция подсветки товаров без остатка - работает много раз чтобы поймать все товары
    function highlightProducts() {
        console.log('[Подсветка] Начинаем поиск товаров для подсветки...');
        
        // Повторяем проверку несколько раз чтобы поймать все товары
        var attempts = 0;
        var maxAttempts = 5;
        
        function checkAndHighlight() {
            attempts++;
            console.log('[Подсветка] Попытка ' + attempts + ' из ' + maxAttempts);
            
            var options = document.querySelectorAll('.select2-results__option:not([role="group"])');
            console.log('[Подсветка] Найдено товаров в списке:', options.length);
            
            // Убираем старые красные цвета с каждого товара
            options.forEach(function(option) {
                option.classList.remove('no-stock');
                option.style.backgroundColor = '';
                option.style.color = '';
                option.style.borderLeft = '';
            });
            
            // Проверяем каждый товар и красим те где написано "Недостат."
            var foundNoStock = 0;
            options.forEach(function(option, index) {
                var text = option.textContent || option.innerText || '';
                // Показываем только товары без остатка, остальные не выводим в консоль
                
                // Ищем товары где написано "Недостат."
                if (text.includes('Недостат.')) {
                    // Добавляем класс для красного цвета
                    option.classList.add('no-stock');
                    
                    // И еще добавляем красный цвет напрямую для надежности
                    option.style.backgroundColor = '#FFE6E6';
                    option.style.color = '#CC0000';
                    option.style.borderLeft = '4px solid #FF0000';
                    
                    foundNoStock++;
                    console.log('[Подсветка] ✅ НАШЛИ товар без остатка и покрасили:', text.substring(0, 70));
                } else {
                    // Обычный товар - не выводим в консоль
                }
            });
            
            console.log('[Подсветка] В этой попытке найдено товаров без остатка:', foundNoStock);
            
            // Если еще есть попытки - повторяем проверку через 1 секунду
            if (attempts < maxAttempts) {
                setTimeout(checkAndHighlight, 1000);
            } else {
                console.log('[Подсветка] Закончили все попытки. Итого найдено товаров без остатка:', foundNoStock);
            }
        }
        
        // Начинаем первую проверку через полсекунды
        setTimeout(checkAndHighlight, 500);
    }
        // Добавляем красные стили при загрузке страницы
        addStyles();

        // Слушаем клики по полю выбора товара
        document.addEventListener('click', function(e) {
            if (e.target.closest('select[id*="product"]') ||
                e.target.closest('.select2-container')) {
                
                console.log('[Подсветка] Пользователь кликнул по полю товара');
                highlightProducts();
            }
        });

        // Слушаем прокрутку списка товаров чтобы поймать новые товары которые загружаются
        document.addEventListener('scroll', function(e) {
            if (e.target && e.target.classList && e.target.classList.contains('select2-results')) {
                console.log('[Подсветка] Прокрутили список - ищем новые товары');
                setTimeout(highlightProducts, 800);
            }
        }, {passive: true});
        
        console.log('[Подсветка] Система готова к работе');
    });