from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from account.views import LogoutView, SignupView

app_name = "account"

urlpatterns = [
    path("auth/signup/", SignupView.as_view(), name="signup"),
    path("auth/login/", obtain_auth_token, name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
]
