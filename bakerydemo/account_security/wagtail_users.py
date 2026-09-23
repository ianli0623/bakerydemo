from wagtail.users.apps import WagtailUsersAppConfig


class SecureWagtailUsersAppConfig(WagtailUsersAppConfig):
    group_viewset = "bakerydemo.account_security.group_views.SecureGroupViewSet"
    user_viewset = "bakerydemo.account_security.user_views.SecureUserViewSet"
