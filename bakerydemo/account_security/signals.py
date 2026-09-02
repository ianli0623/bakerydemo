from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .services import sync_password_change

User = get_user_model()


@receiver(pre_save, sender=User)
def detect_password_hash_change(sender, instance, **kwargs):
    if instance.pk is None:
        instance._account_security_password_changed = instance.has_usable_password()
        return

    previous = (
        sender._default_manager.only("password").filter(pk=instance.pk).first()
    )
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
