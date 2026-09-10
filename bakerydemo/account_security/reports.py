from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.utils import timezone

from .services import get_password_expiry_status


def password_expiry_report(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    now = timezone.now()
    expiring_users = []
    users = get_user_model().objects.filter(is_active=True, is_staff=True)

    for user in users:
        status = get_password_expiry_status(user, at=now)
        if status is None or status.warning_level is None or status.remaining_days <= 0:
            continue
        expiring_users.append(
            {
                "user": user,
                "password_changed_at": user.account_security_state.password_changed_at,
                "expires_at": status.expires_at,
                "remaining_days": status.remaining_days,
                "warning_level": status.warning_level,
            }
        )

    expiring_users.sort(key=lambda item: item["expires_at"])
    return render(
        request,
        "account_security/password_expiry_report.html",
        {"expiring_users": expiring_users},
    )
