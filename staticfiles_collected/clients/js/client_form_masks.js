// ERP/clients/static/clients/js/client_form_masks.js

console.log('[ClientFormMasks] Script loaded (v3 - basic with delayed init).');

function initializePhoneMaskBasic(attempt) {
    attempt = attempt || 1;
    console.log('[ClientFormMasks] Attempting basic initialize, attempt #' + attempt);

    if (window.django && window.django.jQuery) {
        console.log('[ClientFormMasks] django.jQuery IS NOW available (attempt #' + attempt + ').');
        
        (function($) { 
            $(document).ready(function() { 
                console.log('[ClientFormMasks] Document ready. Inside django.jQuery wrapper.');
                var phoneField = $('#id_phone');
                
                if (phoneField.length) {
                    var initialValue = phoneField.val(); 
                    console.log('[ClientFormMasks] Phone field (#id_phone) found. Initial value from HTML value attribute: "' + initialValue + '"');
                    
                    if (typeof phoneField.inputmask === 'function') {
                        console.log('[ClientFormMasks] Inputmask plugin IS a function. Applying basic mask...');
                        try {
                            phoneField.inputmask({
                                mask: "+375 (99) 999-99-99",
                                placeholder: "_",
                                showMaskOnHover: false,
                                showMaskOnFocus: true,
                                clearIncomplete: false,
                                jitMasking: true // <--- ДОБАВЬ ЭТУ ОПЦИЮ
                            });
                            console.log('[ClientFormMasks] Inputmask with JIT applied. Value in field after mask: "' + phoneField.val() + '"');
                        } catch (e) {
                            console.error('[ClientFormMasks] Error applying Inputmask:', e);
                        }
                    } else {
                        console.error('[ClientFormMasks] Inputmask plugin is NOT a function. Check if jquery.inputmask.js is loaded and executed correctly BEFORE this script and AFTER jQuery.');
                    }
                } else {
                    console.warn('[ClientFormMasks] Phone field (#id_phone) NOT found in document.ready.');
                }
            });
        })(django.jQuery);

    } else {
        console.warn('[ClientFormMasks] django.jQuery is still NOT available (attempt #' + attempt + '). Retrying in 200ms...');
        if (attempt < 20) { 
            setTimeout(function() {
                initializePhoneMaskBasic(attempt + 1);
            }, 200);
        } else {
            console.error('[ClientFormMasks] django.jQuery did not become available after multiple attempts. Giving up on basic init.');
        }
    }
}

// Начинаем первую попытку инициализации после небольшой задержки
setTimeout(initializePhoneMaskBasic, 100);