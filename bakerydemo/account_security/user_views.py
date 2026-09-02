from django.shortcuts import render
from wagtail.users.views.users import CreateView, UserViewSet

from .forms import TemporaryPasswordUserCreationForm


class TemporaryPasswordCreateView(CreateView):
    def save_action(self):
        if self.expects_json_response:
            return super().save_action()

        return render(
            self.request,
            "account_security/temporary_password_created.html",
            {
                "created_user": self.object,
                "temporary_password": self.form.temporary_password,
            },
        )


class SecureUserViewSet(UserViewSet):
    add_view_class = TemporaryPasswordCreateView

    def get_form_class(self, for_update=False):
        if for_update:
            return super().get_form_class(for_update=True)
        return TemporaryPasswordUserCreationForm
