from django.conf import settings
from django.db import models


class UserSecurityState(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="account_security_state",
    )
    must_change_password = models.BooleanField(default=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PasswordHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_history",
    )
    encoded_password = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["user", "-created_at"])]


class PasskeyCredential(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="passkey_credentials",
    )
    credential_id = models.CharField(max_length=1024, unique=True)
    credential_public_key = models.BinaryField()
    user_handle = models.BinaryField(max_length=64)
    sign_count = models.PositiveBigIntegerField(default=0)
    device_type = models.CharField(max_length=32, blank=True)
    backed_up = models.BooleanField(default=False)
    transports = models.JSONField(default=list, blank=True)
    label = models.CharField(max_length=100, default="Windows Hello")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["user_id", "created_at", "pk"]
        indexes = [
            models.Index(
                fields=["user", "revoked_at"],
                name="passkey_user_active_idx",
            )
        ]


class PasskeyEnrolment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="passkey_enrolments",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_passkey_enrolments",
    )
    code_digest = models.CharField(max_length=64, unique=True)
    disable_password_on_success = models.BooleanField(default=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(
                fields=["user", "expires_at"],
                name="passkey_user_expiry_idx",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(
                    consumed_at__isnull=True,
                    revoked_at__isnull=True,
                ),
                name="passkey_one_pending_per_user",
            )
        ]


class PasskeyAuditEvent(models.Model):
    event_type = models.CharField(max_length=40)
    success = models.BooleanField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="passkey_audit_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="passkey_actions",
    )
    credential = models.ForeignKey(
        PasskeyCredential,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    reason = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["-created_at"], name="passkey_event_time_idx"),
            models.Index(
                fields=["user", "-created_at"],
                name="passkey_event_user_idx",
            ),
        ]
