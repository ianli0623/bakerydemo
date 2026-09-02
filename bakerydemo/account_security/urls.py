from django.urls import path

from . import views

app_name = "account_security"

urlpatterns = [
    path("password/change/", views.password_change, name="password_change"),
]
