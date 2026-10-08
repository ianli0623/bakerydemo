from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from wagtail.admin import messages
from wagtail.users.views.bulk_actions import DeleteBulkAction

from .models import FastIdUserLink

FAST_ID_BULK_DELETE_ERROR = _(
    "Fast-ID-linked users cannot be bulk deleted. Delete them one at a time."
)


class SecureDeleteBulkAction(DeleteBulkAction):
    template_name = "account_security/confirm_bulk_user_delete.html"

    @staticmethod
    def contains_fast_id_user(objects):
        return FastIdUserLink.objects.filter(
            user_id__in=[obj.pk for obj in objects]
        ).exists()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_users = [item["item"] for item in context["items"]]
        selected_users.extend(context["items_with_no_access"])
        if self.contains_fast_id_user(selected_users):
            context["fast_id_bulk_delete_blocked"] = True
            context["is_protected"] = True
        return context

    def prepare_action(self, objects, objects_without_access):
        selected_users = [
            *objects,
            *objects_without_access["items_with_no_access"],
        ]
        if self.contains_fast_id_user(selected_users):
            messages.error(self.request, FAST_ID_BULK_DELETE_ERROR)
            return redirect(self.next_url)
        return super().prepare_action(objects, objects_without_access)
