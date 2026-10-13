from django.urls import path

from .views import (
    EmailResendView,
    EmailVerifyView,
    NotificationSettingsView,
    LoginView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
)

urlpatterns = [
    path("auth/email/verify/", EmailVerifyView.as_view(), name="auth-email-verify"),
    path("auth/email/resend/", EmailResendView.as_view(), name="auth-email-resend"),
    path("settings/notifications/", NotificationSettingsView.as_view(), name="notification-settings"),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path(
        "auth/password-reset/request/",
        PasswordResetRequestView.as_view(),
        name="auth-password-reset-request",
    ),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
]
