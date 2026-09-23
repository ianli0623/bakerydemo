import unicodedata

from django.db import migrations


INDEX_NAME = "account_security_auth_user_email_ci_uniq"


def normalize_existing_emails(apps, schema_editor):
    user_model = apps.get_model("auth", "User")

    for user in user_model.objects.exclude(email="").only("pk", "email").iterator():
        normalized_email = unicodedata.normalize("NFKC", user.email).strip().casefold()
        if normalized_email != user.email:
            user_model.objects.filter(pk=user.pk).update(email=normalized_email)


def create_case_insensitive_email_index(apps, schema_editor):
    user_model = apps.get_model("auth", "User")
    quote_name = schema_editor.quote_name
    table_name = quote_name(user_model._meta.db_table)
    email_column = quote_name(user_model._meta.get_field("email").column)
    index_name = quote_name(INDEX_NAME)

    schema_editor.execute(
        f"CREATE UNIQUE INDEX {index_name} "
        f"ON {table_name} (LOWER({email_column})) "
        f"WHERE {email_column} <> ''"
    )


def drop_case_insensitive_email_index(apps, schema_editor):
    schema_editor.execute(
        f"DROP INDEX IF EXISTS {schema_editor.quote_name(INDEX_NAME)}"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("account_security", "0004_passkeyenrolment_passkey_one_pending_per_user"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(normalize_existing_emails, migrations.RunPython.noop),
        migrations.RunPython(
            create_case_insensitive_email_index,
            drop_case_insensitive_email_index,
        ),
    ]
