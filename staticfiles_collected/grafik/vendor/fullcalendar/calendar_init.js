document.addEventListener('DOMContentLoaded', function() {
    // Получаем список пустых дат и нужный цвет из Django (эти переменные должны быть определены в шаблоне выше!)
    var emptyDays = typeof emptyDays !== "undefined" ? emptyDays : [];
    var emptyHex = typeof emptyHex !== "undefined" ? emptyHex : "#FFCCCC";

    var calendarEl = document.getElementById('calendar');
    if (!calendarEl) return;
    var eventsUrl = calendarEl.dataset.eventsUrl;

    var calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
        },
        locale: 'ru',
        buttonText: {
            today: 'Сегодня',
            month: 'Месяц',
            week: 'Неделя',
            day: 'День',
            list: 'Список'
        },
        events: eventsUrl,
        // --- Подсветка дней без смен ---
        dayCellDidMount: function(info) {
            // Преобразуем дату ячейки в формат YYYY-MM-DD
            var d = info.date.toISOString().slice(0, 10);
            if (emptyDays.includes(d)) {
                info.el.style.backgroundColor = emptyHex;
            }
        },
        // --- ТВОЙ КОД для кастомного отображения событий ---
        eventContent: function(arg) {
            let employeeName = arg.event.extendedProps.employee_name || arg.event.title;
            let shiftTime = arg.event.extendedProps.shift_time_str;
            let innerHtml = `<div class="fc-event-main-custom-frame">`;
            innerHtml += `<div class="fc-event-employee-name">${employeeName}</div>`;
            if (shiftTime) {
                innerHtml += `<div class="fc-event-shift-time">${shiftTime}</div>`;
            }
            innerHtml += `</div>`;
            return { html: innerHtml };
        }
    });

    calendar.render();

    // --- ТВОЯ функция для исправления цветов (если нужна) ---
    function fixEventColors() {
        if (document.body.classList.contains('theme-dark')) {
            document.querySelectorAll('.fc-event-employee-name, .fc-event-shift-time').forEach(el => {
                el.style.setProperty('color', '#e3f2fd', 'important');
                el.style.setProperty('text-shadow', '0 1px 2px #000', 'important');
            });
        }
    }

    var observer = new MutationObserver(fixEventColors);
    observer.observe(calendarEl, { childList: true, subtree: true });

    calendar.on('eventDidMount', fixEventColors);
    calendar.on('datesSet', fixEventColors);

    fixEventColors();
});