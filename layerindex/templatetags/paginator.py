from django import template
from django.http import HttpRequest
from django.core.paginator import Paginator

register = template.Library()


# Return new page URL for the current view.
# Usage: {% page_url request 2 %}
@register.simple_tag
def page_url(request: "HttpRequest", page: int) -> "str":
    new_query = request.GET.copy()
    new_query['page'] = f'{page}'
    return '?' + new_query.urlencode()


# Return elided page range for the current page object.
# Usage: {% page_obj|elided_page_range  %}
@register.filter
def elided_page_range(page_obj: "Paginator.page") -> "list[int]":
    if not isinstance(page_obj.paginator, Paginator):
        return []

    return page_obj.paginator.get_elided_page_range(
        number=page_obj.number,
        on_each_side=3,
        on_ends=1,
    )