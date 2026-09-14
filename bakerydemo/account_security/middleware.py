from django.conf import settings
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from wagtail.admin import messages

from .services import (
    get_password_expiry_status,
    get_security_state,
    password_is_expired,
)
from .views import RETURN_TO_SESSION_KEY

ALLOWED_URL_NAMES = {
    "admin:logout",
    "wagtailadmin_javascript_catalog",
    "wagtailadmin_logout",
    "wagtailadmin_sprite",
}
LEGACY_PASSWORD_CHANGE_URL_NAMES = {
    "admin:password_change",
}
PASSWORD_EXPIRY_NOTICE_SESSION_KEY = "account_security_password_expiry_notice"


def is_passkey_only_user(user):
    return (
        not user.has_usable_password()
        and user.passkey_credentials.filter(revoked_at__isnull=True).exists()
    )


class PasswordPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if not user.is_authenticated or not (user.is_staff or user.is_superuser):
            return self.get_response(request)

        change_url = reverse("account_security:password_change")
        if request.path_info == change_url:
            return self.get_response(request)

        protected_prefixes = getattr(
            settings,
            "ACCOUNT_SECURITY_PROTECTED_PREFIXES",
            ("/admin/", "/django-admin/"),
        )
        if not request.path_info.startswith(tuple(protected_prefixes)):
            return self.get_response(request)

        if is_passkey_only_user(user):
            return self.get_response(request)

        try:
            view_name = resolve(request.path_info).view_name
        except Resolver404:
            view_name = None

        if view_name in LEGACY_PASSWORD_CHANGE_URL_NAMES:
            return redirect("account_security:password_change")
        if view_name in ALLOWED_URL_NAMES:
            return self.get_response(request)

        state = get_security_state(user)
        if state.must_change_password or password_is_expired(user):
            request.session[RETURN_TO_SESSION_KEY] = request.get_full_path()
            return redirect("account_security:password_change")

        self._add_password_expiry_notice(request, change_url)

        return self.get_response(request)

    def _add_password_expiry_notice(self, request, change_url):
        status = get_password_expiry_status(request.user)
        if status is None or status.warning_level is None:
            return

        marker = f"{status.expires_at.isoformat()}:{status.warning_level}"
        if request.session.get(PASSWORD_EXPIRY_NOTICE_SESSION_KEY) == marker:
            return

        expiry_date = timezone.localtime(status.expires_at).strftime("%Y/%m/%d")
        message = _(
            "Your password will expire on %(date)s. %(days)d days remaining."
        ) % {
            "date": expiry_date,
            "days": status.remaining_days,
        }
        buttons = [messages.button(change_url, _("Change password now"))]
        if status.warning_level == "critical":
            messages.error(request, message, buttons=buttons)
        else:
            messages.warning(request, message, buttons=buttons)

        request.session[PASSWORD_EXPIRY_NOTICE_SESSION_KEY] = marker
