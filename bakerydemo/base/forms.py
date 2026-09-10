from wagtail.admin.forms.account import (
    AvatarPreferencesForm,
    NotificationPreferencesForm,
    ThemePreferencesForm,
)


class ResettableAvatarPreferencesForm(AvatarPreferencesForm):
    def clean_avatar(self):
        if self.cleaned_data.get("avatar") is False:
            return False

        return super().clean_avatar()


class SimplifiedThemePreferencesForm(ThemePreferencesForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("keyboard_shortcuts", None)


class HiddenNotificationPreferencesForm(NotificationPreferencesForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.clear()
