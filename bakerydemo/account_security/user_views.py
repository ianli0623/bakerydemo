from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from wagtail.admin.ui.tables import Column
from wagtail.users.views.users import (
    CreateView,
    EditView,
    HistoryView,
    IndexView,
    UserColumn,
    UserViewSet,
)

from .forms import SecureUserEditForm, TemporaryPasswordUserCreationForm
from .passkeys import create_enrolment, record_passkey_event
from .services import get_security_state


@method_decorator(never_cache, name="dispatch")
class TemporaryPasswordCreateView(CreateView):
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["for_user"] = self.request.user
        return kwargs

    def save_action(self):
        if self.expects_json_response:
            return super().save_action()

        authentication_method = self.form.cleaned_data["authentication_method"]
        if (
            authentication_method
            == TemporaryPasswordUserCreationForm.AUTHENTICATION_METHOD_WINDOWS_HELLO
        ):
            if not self.request.user.is_superuser:
                raise PermissionDenied
            state = get_security_state(self.object)
            state.must_change_password = False
            state.password_changed_at = None
            state.save(
                update_fields=[
                    "must_change_password",
                    "password_changed_at",
                    "updated_at",
                ]
            )
            enrolment, raw_code = create_enrolment(
                self.object,
                self.request.user,
                disable_password_on_success=True,
            )
            record_passkey_event(
                "enrolment_created",
                success=True,
                user=self.object,
                actor=self.request.user,
                request=self.request,
            )
            return render(
                self.request,
                "account_security/passkey_enrolment_created.html",
                {
                    "created_user": self.object,
                    "enrolment": enrolment,
                    "enrolment_code": raw_code,
                },
            )

        return render(
            self.request,
            "account_security/temporary_password_created.html",
            {
                "created_user": self.object,
                "temporary_password": self.form.temporary_password,
            },
        )


class SecureUserIndexView(IndexView):
    @cached_property
    def columns(self):
        columns = list(super().columns)
        title_column_class = self._get_title_column_class(UserColumn)
        columns[1] = title_column_class(
            "email",
            accessor="email",
            label=_("Email (account ID)"),
            sort_key="email",
            get_url=self.get_edit_url,
            classname="email",
        )
        columns[2] = Column(
            "username",
            accessor="get_username",
            label=_("Alias / display name"),
            sort_key="username",
            classname="username",
            width="20%",
        )
        return columns


class AliasUserEditView(EditView):
    def get_page_subtitle(self):
        return self.object.get_username()


class AliasUserHistoryView(HistoryView):
    def get_page_subtitle(self):
        return self.object.get_username()


class SecureUserViewSet(UserViewSet):
    ordering = "email"
    index_view_class = SecureUserIndexView
    add_view_class = TemporaryPasswordCreateView
    edit_view_class = AliasUserEditView
    history_view_class = AliasUserHistoryView
    create_template_name = "account_security/user_create.html"
    edit_template_name = "account_security/user_edit.html"

    def get_form_class(self, for_update=False):
        if for_update:
            return SecureUserEditForm
        return TemporaryPasswordUserCreationForm
