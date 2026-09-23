from django import template
from django.utils.translation import gettext
from wagtail.users.templatetags.wagtailusers_tags import (
    format_permissions as wagtail_format_permissions,
)

register = template.Library()


@register.inclusion_tag("wagtailusers/groups/includes/formatted_permissions.html")
def format_group_permissions(permission_bound_field):
    context = wagtail_format_permissions(permission_bound_field)
    for permission_group in context["object_perms"]:
        permission_group["object"] = gettext(str(permission_group["object"]))
    return context
