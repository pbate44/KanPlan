from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(value, css_class):
    """
    Add a CSS class to form field
    Usage: {{ form.field|add_class:"form-control" }}
    """
    return value.as_widget(attrs={"class": css_class})
