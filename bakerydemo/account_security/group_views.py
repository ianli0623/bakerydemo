from wagtail.users.views.groups import GroupViewSet

from .group_forms import SecureGroupForm


class SecureGroupViewSet(GroupViewSet):
    def get_form_class(self, for_update=False):
        return SecureGroupForm
