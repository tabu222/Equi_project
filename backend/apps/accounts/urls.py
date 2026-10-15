from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path("auth/login", views.LoginView.as_view(), name="login"),
    path("auth/register", views.RegisterView.as_view(), name="register"),
    path("auth/google", views.GoogleLoginView.as_view(), name="google-login"),
    path("auth/refresh", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/me", views.MeView.as_view(), name="me"),
    path("users", views.UserListCreateView.as_view(), name="user-list"),
    path("users/<int:user_id>", views.UserDetailView.as_view(), name="user-detail"),
]
