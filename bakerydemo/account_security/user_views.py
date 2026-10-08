from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from wagtail.admin.ui.tables import Column
from wagtail.users.views.users import (
    CreateView,
    DeleteView,
    EditView,
    HistoryView,
    IndexView,
    UserColumn,
    UserViewSet,
)

from .fast_id import FastIdError
from .forms import SecureUserEditForm, TemporaryPasswordUserCreationForm
from .models import FastIdUserLink
from .passkey_providers import get_passkey_provider
from .passkeys import PasskeyCeremonyError, create_enrolment, record_passkey_event
from .services import get_security_state

FAST_ID_PROVISIONING_ERROR = _(
    "The Fast-ID account could not be created. Please try again."
)
FAST_ID_DELETION_ERROR = _(
    "The Fast-ID account could not be deleted. The local user was kept."
)
PASSKEY_CLEANUP_REMINDER = _(
    "After deleting the account, remove the lularm.com passkey in Windows "
    "Settings > Accounts > Passkeys to avoid duplicate passkeys later."
)
FAST_ID_DISABLED_DELETION_ERROR = _(
    "Fast-ID is disabled, so a linked account cannot be deleted safely. "
    "Enable Fast-ID first."
)
LOCAL_DELETION_ERROR = _(
    "The Fast-ID account was deleted, but the local account could not be "
    "removed and has been disabled. Try deleting it again."
)


@method_decorator(never_cache, name="dispatch")
class TemporaryPasswordCreateView(CreateView):
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["for_user"] = self.request.user
        return kwargs

    def save_instance(self):
        instance = super().save_instance()
        authentication_method = self.form.cleaned_data["authentication_method"]
        if (
            settings.FAST_ID_ENABLED
            and authentication_method
            == TemporaryPasswordUserCreationForm.AUTHENTICATION_METHOD_WINDOWS_HELLO
        ):
            get_passkey_provider().provision_user(instance)
        return instance

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except (FastIdError, PasskeyCeremonyError):
            self.object = None
            self.produced_error_code = "fast_id_provisioning_failed"
            self.produced_error_message = FAST_ID_PROVISIONING_ERROR
            form.add_error(None, FAST_ID_PROVISIONING_ERROR)
            return self.form_invalid(form)

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


class FastIdUserDeleteView(DeleteView):
    @cached_property
    def has_fast_id_link(self):
        return FastIdUserLink.objects.filter(user=self.object).exists()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["show_passkey_cleanup_reminder"] = self.has_fast_id_link
        context["show_fast_id_deletion_warning"] = (
            self.has_fast_id_link and settings.FAST_ID_ENABLED
        )
        context["fast_id_deletion_blocked"] = (
            self.has_fast_id_link and not settings.FAST_ID_ENABLED
        )
        return context

    def delete_action(self):
        has_fast_id_link = self.has_fast_id_link
        if has_fast_id_link:
            if not settings.FAST_ID_ENABLED:
                raise PasskeyCeremonyError("fast_id_disabled")
            was_active = self.object.is_active
            type(self.object)._default_manager.filter(pk=self.object.pk).update(
                is_active=False
            )
            self.object.is_active = False
            try:
                get_passkey_provider().deprovision_user(self.object)
            except (FastIdError, PasskeyCeremonyError):
                type(self.object)._default_manager.filter(pk=self.object.pk).update(
                    is_active=was_active
                )
                self.object.is_active = was_active
                raise
            self.fast_id_deprovisioned = True
        super().delete_action()

    def form_valid(self, form):
        if self.has_fast_id_link and not settings.FAST_ID_ENABLED:
            messages.error(self.request, FAST_ID_DISABLED_DELETION_ERROR)
            return self.form_invalid(form)
        try:
            response = super().form_valid(form)
        except (FastIdError, PasskeyCeremonyError):
            messages.error(self.request, FAST_ID_DELETION_ERROR)
            return self.form_invalid(form)
        except DatabaseError:
            if not getattr(self, "fast_id_deprovisioned", False):
                raise
            messages.error(self.request, LOCAL_DELETION_ERROR)
            return self.form_invalid(form)
        if self.has_fast_id_link:
            messages.warning(self.request, PASSKEY_CLEANUP_REMINDER)
        return response


class SecureUserViewSet(UserViewSet):
    ordering = "email"
    index_view_class = SecureUserIndexView
    add_view_class = TemporaryPasswordCreateView
    edit_view_class = AliasUserEditView
    delete_view_class = FastIdUserDeleteView
    history_view_class = AliasUserHistoryView
    create_template_name = "account_security/user_create.html"
    edit_template_name = "account_security/user_edit.html"
    delete_template_name = "account_security/confirm_user_delete.html"

    def get_form_class(self, for_update=False):
        if for_update:
            return SecureUserEditForm
        return TemporaryPasswordUserCreationForm
