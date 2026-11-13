from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Custom template filter to safely fetch a key from a dictionary.
    Usage in template: {{ my_dict|get_item:key_variable }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''

@register.filter(name='star_html')
def star_html(rating):
    """
    Renders gold stars (★) and gray stars (★) based on rating (0 to 5).
    """
    try:
        r = int(round(float(rating)))
    except (ValueError, TypeError):
        r = 0
    r = max(0, min(5, r))
    gold = '<span style="color: #F59E0B;">' + '★' * r + '</span>'
    gray = '<span style="color: #D1D5DB;">' + '★' * (5 - r) + '</span>'
    return mark_safe(gold + gray)
