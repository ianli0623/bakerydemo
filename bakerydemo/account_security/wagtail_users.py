from wagtail.users.apps import WagtailUsersAppConfig


class SecureWagtailUsersAppConfig(WagtailUsersAppConfig):
    user_viewset = "bakerydemo.account_security.user_views.SecureUserViewSet"
