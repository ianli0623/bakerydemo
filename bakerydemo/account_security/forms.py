from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from wagtail.admin.forms.auth import LoginForm as WagtailLoginForm

from .services import set_user_password

GENERIC_LOGIN_ERROR = _(
    "The username or password is incorrect, or this account is temporarily unavailable."
)


class SecurityAdminAuthenticationForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": GENERIC_LOGIN_ERROR,
        "inactive": GENERIC_LOGIN_ERROR,
    }


class SecurityWagtailLoginForm(WagtailLoginForm):
    error_messages = {
        **WagtailLoginForm.error_messages,
        "invalid_login": GENERIC_LOGIN_ERROR,
        "inactive": GENERIC_LOGIN_ERROR,
    }


class SecurityPasswordChangeForm(forms.Form):
    old_password = forms.CharField(
        label=_("Current password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    new_password1 = forms.CharField(
        label=_("New password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    new_password2 = forms.CharField(
        label=_("Confirm new password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        value = self.cleaned_data["old_password"]
        if not self.user.check_password(value):
            raise ValidationError(
                _("The current password is incorrect."),
                code="invalid",
            )
        return value

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("new_password1")
        password2 = cleaned_data.get("new_password2")
        if password1 and password2 and password1 != password2:
            self.add_error(
                "new_password2",
                _("The two password fields did not match."),
            )
        elif password1:
            try:
                validate_password(password1, user=self.user)
            except ValidationError as error:
                self.add_error("new_password1", error)
        return cleaned_data

    def save(self):
        return set_user_password(
            self.user,
            self.cleaned_data["new_password1"],
            must_change_password=False,
        )
