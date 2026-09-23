from axes.handlers.proxy import AxesProxyHandler
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .authentication import normalize_account_email
from .services import sync_password_change

User = get_user_model()


@receiver(pre_save, sender=User)
def detect_password_hash_change(sender, instance, **kwargs):
    if instance.pk is None:
        instance._account_security_password_changed = instance.has_usable_password()
        return

    previous = sender._default_manager.only("password").filter(pk=instance.pk).first()
    instance._account_security_password_changed = (
        previous is not None and previous.password != instance.password
    )


@receiver(post_save, sender=User)
def secure_changed_password(sender, instance, created, **kwargs):
    password_changed = created or getattr(
        instance, "_account_security_password_changed", False
    )
    if password_changed:
        sync_password_change(instance, must_change_password=True)


@receiver(user_logged_in, dispatch_uid="account_security_reset_email_attempts")
def reset_email_login_attempts(sender, request, user, **kwargs):
    account_email = normalize_account_email(user.email)
    if account_email:
        AxesProxyHandler.reset_attempts(username=account_email)
