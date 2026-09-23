import unicodedata

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


def normalize_account_email(value):
    if not isinstance(value, str):
        return value
    return unicodedata.normalize("NFKC", value).strip().casefold()


def normalize_login_username(request, credentials=None):
    username_field = getattr(settings, "AXES_USERNAME_FORM_FIELD", "username")
    username = (credentials or {}).get(username_field)
    if username is None:
        username = request.POST.get(username_field)
    return normalize_account_email(username)


class EmailAuthenticationBackend(ModelBackend):
    """Authenticate admin users by their case-insensitive email account ID."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        account_email = username
        if account_email is None:
            account_email = kwargs.get("email")
        account_email = normalize_account_email(account_email)
        if not account_email or password is None:
            return None

        user_model = get_user_model()
        try:
            user = user_model._default_manager.get(email__iexact=account_email)
        except (user_model.DoesNotExist, user_model.MultipleObjectsReturned):
            user_model().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
