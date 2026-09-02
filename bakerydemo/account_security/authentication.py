import unicodedata

from django.conf import settings


def normalize_login_username(request, credentials=None):
    username_field = getattr(settings, "AXES_USERNAME_FORM_FIELD", "username")
    username = (credentials or {}).get(username_field)
    if username is None:
        username = request.POST.get(username_field)
    if not isinstance(username, str):
        return username
    return unicodedata.normalize("NFKC", username).casefold()
