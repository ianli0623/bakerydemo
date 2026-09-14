import secrets
import string

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import (
    password_validators_help_text_html,
    validate_password,
)
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from wagtail.admin.forms.auth import LoginForm as WagtailLoginForm
from wagtail.users.forms import UserCreationForm

from .services import set_user_password

GENERIC_LOGIN_ERROR = _(
    "The username or password is incorrect, or this account is temporarily unavailable."
)

TEMPORARY_PASSWORD_LENGTH = 20
TEMPORARY_PASSWORD_SYMBOLS = "!@#$%^*-_=+"


def generate_temporary_password(user):
    character_groups = (
        string.ascii_uppercase,
        string.ascii_lowercase,
        string.digits,
        TEMPORARY_PASSWORD_SYMBOLS,
    )
    alphabet = "".join(character_groups)
    random_source = secrets.SystemRandom()

    while True:
        characters = [secrets.choice(group) for group in character_groups]
        characters.extend(
            secrets.choice(alphabet)
            for _ in range(TEMPORARY_PASSWORD_LENGTH - len(character_groups))
        )
        random_source.shuffle(characters)
        password = "".join(characters)
        try:
            validate_password(password, user=user)
        except ValidationError:
            continue
        return password


class TemporaryPasswordUserCreationForm(UserCreationForm):
    AUTHENTICATION_METHOD_WINDOWS_HELLO = "windows_hello"
    AUTHENTICATION_METHOD_TEMPORARY_PASSWORD = "temporary_password"

    authentication_method = forms.ChoiceField(
        label=_("Authentication method"),
        choices=(
            (
                AUTHENTICATION_METHOD_WINDOWS_HELLO,
                _("Windows Hello (passwordless)"),
            ),
            (
                AUTHENTICATION_METHOD_TEMPORARY_PASSWORD,
                _("Temporary password"),
            ),
        ),
        initial=AUTHENTICATION_METHOD_WINDOWS_HELLO,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields["password1"]
        del self.fields["password2"]

    def save(self, commit=True):
        user = forms.ModelForm.save(self, commit=False)
        authentication_method = self.cleaned_data["authentication_method"]
        self.temporary_password = None
        if authentication_method == self.AUTHENTICATION_METHOD_WINDOWS_HELLO:
            user.set_unusable_password()
        else:
            self.temporary_password = generate_temporary_password(user)
            user.set_password(self.temporary_password)

        if commit:
            user.save()
            self.save_m2m()
        return user


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
        self.fields["new_password1"].help_text = password_validators_help_text_html()

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
