from django.conf import settings
from django.db import migrations
from django.utils import timezone


def bootstrap_existing_users(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)
    State = apps.get_model("account_security", "UserSecurityState")
    History = apps.get_model("account_security", "PasswordHistory")
    migrated_at = timezone.now()

    for user in User.objects.iterator():
        State.objects.get_or_create(
            user_id=user.pk,
            defaults={
                "must_change_password": False,
                "password_changed_at": migrated_at,
            },
        )
        if user.password and not user.password.startswith("!"):
            History.objects.get_or_create(
                user_id=user.pk,
                encoded_password=user.password,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("account_security", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(
            bootstrap_existing_users,
            reverse_code=migrations.RunPython.noop,
        )
    ]
