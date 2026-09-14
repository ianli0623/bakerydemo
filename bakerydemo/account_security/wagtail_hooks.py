from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.menu import MenuItem

from .passkey_views import (
    passkey_generate_enrolment,
    passkey_management,
    passkey_revoke,
)
from .reports import password_expiry_report


class PasswordExpiryReportMenuItem(MenuItem):
    def is_shown(self, request):
        return request.user.is_superuser


class PasskeyManagementReportMenuItem(MenuItem):
    def is_shown(self, request):
        return request.user.is_superuser


@hooks.register("register_admin_urls")
def register_account_security_report_urls():
    return [
        path(
            "reports/password-expiry/",
            password_expiry_report,
            name="account_security_password_expiry_report",
        ),
        path(
            "reports/windows-hello/",
            passkey_management,
            name="account_security_passkey_management",
        ),
        path(
            "reports/windows-hello/users/<int:user_id>/enrolment/",
            passkey_generate_enrolment,
            name="account_security_passkey_generate_enrolment",
        ),
        path(
            "reports/windows-hello/credentials/<int:credential_id>/revoke/",
            passkey_revoke,
            name="account_security_passkey_revoke",
        ),
    ]


@hooks.register("register_reports_menu_item")
def register_password_expiry_report_menu_item():
    return PasswordExpiryReportMenuItem(
        _("Password expiry reminders"),
        reverse("account_security_password_expiry_report"),
        name="password-expiry-reminders",
        icon_name="date",
        order=600,
    )


@hooks.register("register_reports_menu_item")
def register_passkey_management_report_menu_item():
    return PasskeyManagementReportMenuItem(
        _("Windows Hello management"),
        reverse("account_security_passkey_management"),
        name="windows-hello-management",
        icon_name="user",
        order=610,
    )
