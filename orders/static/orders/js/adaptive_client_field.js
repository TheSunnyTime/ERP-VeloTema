// ERP/orders/static/orders/js/adaptive_client_field.js
(function($) {
    $(document).ready(function() {
        console.log('[AdaptiveField] Document ready. Initializing adaptive width for client field...');
        var clientFieldSelector = '#id_client';

        // ... (getStylePropertyValue остается без изменений) ...
        function getStylePropertyValue(element, propertyName) {
            if (!element) return '';
            if (element.currentStyle) {
                return element.currentStyle[propertyName];
            } else if (window.getComputedStyle) {
                return document.defaultView.getComputedStyle(element, null).getPropertyValue(propertyName);
            }
            return '';
        }


        // ... (adaptSelect2Width остается почти без изменений, только добавим лог в начале) ...
        function adaptSelect2Width(selectElement) {
            console.log('[AdaptiveField] adaptSelect2Width called for:', selectElement);
            var $selectElement = $(selectElement);
            // Эта проверка уже есть, но оставим для ясности
            if (!$selectElement.length || !$selectElement.is(':visible')) {
                // Если select скрыт (как select2-hidden-accessible), то is(':visible') будет false.
                // Нам важно, чтобы $selectElement.length был > 0
                if (!$selectElement.length) {
                    console.log('[AdaptiveField] Original select element NOT FOUND in adaptSelect2Width:', selectElement);
                    return;
                }
                console.log('[AdaptiveField] Original select element found, visible state:', $selectElement.is(':visible'));
            }

            var $select2Container = $selectElement.next('.select2-container');
            if (!$select2Container.length) {
                console.log('[AdaptiveField] Select2 container not found as next sibling for:', selectElement);
                // Попробуем найти его по data-select2-id атрибуту оригинального select
                var select2DataId = $selectElement.attr('data-select2-id');
                if (select2DataId) {
                    // Ищем контейнер, который aria-owns этот ID или связан иначе
                     $select2Container = $('[aria-owns="select2-' + select2DataId + '-results"]').closest('.select2-container');
                     if ($select2Container.length) {
                        console.log('[AdaptiveField] Found Select2 container via aria-owns for data-select2-id:', select2DataId);
                     } else {
                        // Еще одна попытка, если data-select2-id это ID контейнера
                        $select2Container = $('#select2-' + select2DataId + '-container').closest('.select2-container');
                        if($select2Container.length) {
                            console.log('[AdaptiveField] Found Select2 container via #select2-ID-container for data-select2-id:', select2DataId);
                        } else {
                            console.log('[AdaptiveField] Select2 container still not found using data-select2-id for:', selectElement);
                            return;
                        }
                     }
                } else {
                    console.log('[AdaptiveField] data-select2-id not found on original select. Cannot find container.');
                    return;
                }
            }  else {
                 console.log('[AdaptiveField] Found Select2 container as next sibling for:', selectElement);
            }

            var $renderedSelection = $select2Container.find('.select2-selection__rendered');
            if (!$renderedSelection.length) {
                $renderedSelection = $select2Container.find('.select2-chosen'); // Для старых версий
                if (!$renderedSelection.length) {
                    console.log('[AdaptiveField] Rendered selection (.select2-selection__rendered or .select2-chosen) not found in Select2 container for:', selectElement);
                    return;
                } else {
                    console.log('[AdaptiveField] Found .select2-chosen for:', selectElement);
                }
            } else {
                 console.log('[AdaptiveField] Found .select2-selection__rendered for:', selectElement);
            }

            var text = $renderedSelection.text() || $renderedSelection.attr('title');
            if (!text && $selectElement.find('option:selected').length) {
                text = $selectElement.find('option:selected').text();
            }
            
            console.log('[AdaptiveField] Text to measure for', selectElement, 'is:', '"' + text + '"');

            if (!text || text.trim() === "" || text.trim() === "---------") {
                // $select2Container.css('width', ''); // Можно сбросить или установить минимальную
                $select2Container.css('width', '250px'); // Установим разумную ширину по умолчанию
                console.log('[AdaptiveField] No significant text, set default width for', selectElement);
                return;
            }

            var $tempSpan = $('<span>').css({
                position: 'absolute',
                visibility: 'hidden',
                whiteSpace: 'pre',
                fontSize: getStylePropertyValue($renderedSelection[0], 'font-size'),
                fontFamily: getStylePropertyValue($renderedSelection[0], 'font-family'),
                fontWeight: getStylePropertyValue($renderedSelection[0], 'font-weight'),
                letterSpacing: getStylePropertyValue($renderedSelection[0], 'letter-spacing'),
                paddingLeft: getStylePropertyValue($renderedSelection[0], 'padding-left'),
                paddingRight: getStylePropertyValue($renderedSelection[0], 'padding-right')
            }).text(text);

            $('body').append($tempSpan);
            var contentWidth = $tempSpan.width();
            $tempSpan.remove();
            console.log('[AdaptiveField] Measured contentWidth:', contentWidth);

            var buffer = 50; 
            var newWidth = contentWidth + buffer;
            var minWidth = 200; 

            $select2Container.css('width', Math.max(newWidth, minWidth) + 'px');
            console.log('[AdaptiveField] Set width to', Math.max(newWidth, minWidth) + 'px for', selectElement);
        }

        function applyWhenReady(attempt) {
            attempt = attempt || 1;
            console.log('[AdaptiveField] applyWhenReady attempt:', attempt);

            var $clientField = $(clientFieldSelector);

            if ($clientField.length) {
                console.log('[AdaptiveField] Element', clientFieldSelector, 'found in DOM. Has select2 data?', !!$clientField.data('select2'), 'Is hidden-accessible?', $clientField.hasClass("select2-hidden-accessible"));
                
                // Проверяем, инициализирован ли Select2 на элементе
                // Django admin Select2 может не всегда добавлять .data('select2')
                // но он добавляет класс 'select2-hidden-accessible' к оригинальному select
                if ($clientField.hasClass("select2-hidden-accessible")) {
                    console.log('[AdaptiveField] Select2 is considered ready for', clientFieldSelector, '(found class select2-hidden-accessible)');
                    adaptSelect2Width(clientFieldSelector); 
                    
                    $clientField.off('change.adaptiveWidth').on('change.adaptiveWidth', function() {
                        console.log('[AdaptiveField] Change event triggered for', clientFieldSelector);
                        setTimeout(function() {
                            adaptSelect2Width(clientFieldSelector);
                        }, 150); 
                    });
                } else {
                    if (attempt < 25) { // Пробуем 25 раз (5 секунд)
                        console.log('[AdaptiveField] Select2 not yet fully ready for', clientFieldSelector, '(class select2-hidden-accessible not found), retrying...');
                        setTimeout(function() { applyWhenReady(attempt + 1); }, 200);
                    } else {
                        console.log('[AdaptiveField] Select2 did not become ready for', clientFieldSelector, 'after multiple attempts.');
                    }
                }
            } else {
                if (attempt < 25) {
                    console.log('[AdaptiveField] Client field selector NOT found on page:', clientFieldSelector, 'Retrying attempt:', attempt);
                    setTimeout(function() { applyWhenReady(attempt + 1); }, 200);
                } else {
                     console.log('[AdaptiveField] Client field selector NOT found on page:', clientFieldSelector, 'after multiple attempts. Giving up.');
                }
            }
        }
        
        applyWhenReady(); // Начинаем проверку
        
    });
})(django.jQuery);