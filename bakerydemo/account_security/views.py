from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _

from .forms import SecurityPasswordChangeForm

RETURN_TO_SESSION_KEY = "account_security_return_to"


def lockout_response(
    request,
    original_response=None,
    credentials=None,
    *args,
    **kwargs,
):
    message = _(
        "The username or password is incorrect, or this account is temporarily unavailable."
    )
    response = render(
        request,
        "account_security/lockout.html",
        {"message": message},
        status=429,
    )
    response.headers["Retry-After"] = "900"
    return response


@login_required(login_url="wagtailadmin_login")
def password_change(request):
    form = SecurityPasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        return_to = request.session.pop(RETURN_TO_SESSION_KEY, None)
        if not return_to or not url_has_allowed_host_and_scheme(
            return_to,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return_to = reverse("wagtailadmin_home")
        return redirect(return_to)

    return render(
        request,
        "account_security/password_change.html",
        {"form": form},
    )
