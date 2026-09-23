from django.contrib.auth import get_user_model
from wagtail.users.forms import GroupForm

VISIBLE_GROUP_PERMISSION_MODELS = {
    ("auth", "group"),
    ("base", "localizedsitecontent"),
    ("base", "sitesettings"),
    ("simple_translation", "simpletranslation"),
    ("wagtailadmin", "admin"),
}


class SecureGroupForm(GroupForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user_meta = get_user_model()._meta
        visible_models = VISIBLE_GROUP_PERMISSION_MODELS | {
            (user_meta.app_label, user_meta.model_name)
        }
        visible_permission_ids = [
            permission.pk
            for permission in self.registered_permissions.select_related("content_type")
            if (
                permission.content_type.app_label,
                permission.content_type.model,
            )
            in visible_models
        ]
        self.registered_permissions = self.registered_permissions.filter(
            pk__in=visible_permission_ids
        )
        self.fields[
            "permissions"
        ].queryset = self.registered_permissions.select_related("content_type")
