from django.urls import path

from . import passkey_views, views

app_name = "account_security"

urlpatterns = [
    path("password/change/", views.password_change, name="password_change"),
    path(
        "windows-hello/enrol/",
        passkey_views.passkey_enrol,
        name="passkey_enrol",
    ),
    path(
        "windows-hello/enrol/options/",
        passkey_views.passkey_registration_options,
        name="passkey_registration_options",
    ),
    path(
        "windows-hello/enrol/verify/",
        passkey_views.passkey_registration_verify,
        name="passkey_registration_verify",
    ),
    path(
        "windows-hello/login/",
        passkey_views.passkey_login,
        name="passkey_login",
    ),
    path(
        "windows-hello/login/options/",
        passkey_views.passkey_authentication_options,
        name="passkey_authentication_options",
    ),
    path(
        "windows-hello/login/verify/",
        passkey_views.passkey_authentication_verify,
        name="passkey_authentication_verify",
    ),
]
