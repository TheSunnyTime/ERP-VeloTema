# utils/templatetags/utils_custom_tags.py
from django import template
from django.utils.html import format_html

register = template.Library()

@register.simple_tag
def display_colored_status(status_key, status_display_name, colors_map):
    """
    Отображает статус с цветным фоном.
    status_key: Ключ статуса (например, Order.STATUS_NEW).
    status_display_name: Отображаемое имя статуса.
    colors_map: Словарь {status_key: hex_color}.
    """
    hex_color = colors_map.get(status_key)
    text_color = '#ffffff' # По умолчанию белый текст

    if hex_color:
        try:
            r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            text_color = '#000000' if luminance > 0.5 else '#FFFFFF'
        except (ValueError, IndexError):
            hex_color = '#dddddd' 
            text_color = '#000000'
        
        return format_html(
            '<span class="status-badge" style="background-color: {0}; color: {1};">{2}</span>',
            hex_color,
            text_color,
            status_display_name
        )
    return status_display_name 