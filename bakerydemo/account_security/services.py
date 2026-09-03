import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone

from .models import PasswordHistory, UserSecurityState

PASSWORD_HISTORY_LIMIT = 3
PASSWORD_EXPIRY_WARNING_DAYS = 30
PASSWORD_EXPIRY_CRITICAL_DAYS = 7


@dataclass(frozen=True)
class PasswordExpiryStatus:
    expires_at: datetime
    remaining_days: int
    warning_level: str | None


def get_security_state(user):
    state, _ = UserSecurityState.objects.get_or_create(
        user=user,
        defaults={
            "must_change_password": True,
            "password_changed_at": None,
        },
    )
    return state


def get_password_expiry_status(user, at=None):
    state = get_security_state(user)
    if state.password_changed_at is None:
        return None

    at = at or timezone.now()
    max_age = timedelta(
        days=getattr(settings, "ACCOUNT_SECURITY_PASSWORD_MAX_AGE_DAYS", 90)
    )
    expires_at = state.password_changed_at + max_age
    remaining_days = math.ceil((expires_at - at).total_seconds() / 86400)

    if remaining_days <= PASSWORD_EXPIRY_CRITICAL_DAYS:
        warning_level = "critical"
    elif remaining_days <= PASSWORD_EXPIRY_WARNING_DAYS:
        warning_level = "warning"
    else:
        warning_level = None

    return PasswordExpiryStatus(
        expires_at=expires_at,
        remaining_days=remaining_days,
        warning_level=warning_level,
    )


def password_is_expired(user, at=None):
    status = get_password_expiry_status(user, at=at)
    return status is None or status.remaining_days <= 0


def _record_current_hash(user):
    if not user.has_usable_password():
        return

    latest = user.password_history.first()
    if latest is None or latest.encoded_password != user.password:
        PasswordHistory.objects.create(user=user, encoded_password=user.password)

    stale_ids = list(
        user.password_history.values_list("pk", flat=True)[PASSWORD_HISTORY_LIMIT:]
    )
    if stale_ids:
        PasswordHistory.objects.filter(pk__in=stale_ids).delete()


@transaction.atomic
def sync_password_change(user, *, must_change_password):
    _record_current_hash(user)
    state = get_security_state(user)
    state.must_change_password = must_change_password
    state.password_changed_at = timezone.now()
    state.save(
        update_fields=[
            "must_change_password",
            "password_changed_at",
            "updated_at",
        ]
    )
    user.account_security_state = state
    return state


@transaction.atomic
def set_user_password(user, raw_password, *, must_change_password):
    validate_password(raw_password, user=user)
    user.set_password(raw_password)
    user.save(update_fields=["password"])
    sync_password_change(user, must_change_password=must_change_password)
    return user
