from wagtail.admin.forms.account import AvatarPreferencesForm


class ResettableAvatarPreferencesForm(AvatarPreferencesForm):
    def clean_avatar(self):
        if self.cleaned_data.get("avatar") is False:
            return False

        return super().clean_avatar()
