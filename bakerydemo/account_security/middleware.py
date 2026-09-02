from django.conf import settings
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse

from .services import get_security_state, password_is_expired
from .views import RETURN_TO_SESSION_KEY

ALLOWED_URL_NAMES = {
    "admin:logout",
    "wagtailadmin_logout",
}
LEGACY_PASSWORD_CHANGE_URL_NAMES = {
    "admin:password_change",
}


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

        return self.get_response(request)
