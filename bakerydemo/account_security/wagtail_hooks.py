from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.menu import MenuItem

from .reports import password_expiry_report


class PasswordExpiryReportMenuItem(MenuItem):
    def is_shown(self, request):
        return request.user.is_superuser


@hooks.register("register_admin_urls")
def register_password_expiry_report_url():
    return [
        path(
            "reports/password-expiry/",
            password_expiry_report,
            name="account_security_password_expiry_report",
        )
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
