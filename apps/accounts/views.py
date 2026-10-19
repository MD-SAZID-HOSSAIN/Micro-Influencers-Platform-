from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.throttling import FailOpenScopedRateThrottle

from .models import Role
from .serializers import (
    DetailSerializer,
    EmailVerifySerializer,
    NotificationSettingsSerializer,
    LoginResponseSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .services import (
    GENERIC_RESET_MESSAGE,
    InvalidCredentials,
    authenticate_login,
    bump_token_version,
    confirm_password_reset,
    issue_access_token,
    request_password_reset,
    resend_email_verification,
    verify_email,
)


class RegisterView(GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [FailOpenScopedRateThrottle]
    throttle_scope = "register"
    serializer_class = RegisterSerializer

    @extend_schema(tags=["Auth"], responses={201: UserSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [FailOpenScopedRateThrottle]
    throttle_scope = "login"
    serializer_class = LoginSerializer

    @extend_schema(tags=["Auth"], responses={200: LoginResponseSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate_login(**serializer.validated_data)
        if user.role == Role.ADMIN:
            raise InvalidCredentials()  # admins use the admin panel login
        return Response(
            {"access": issue_access_token(user), "user": UserSerializer(user).data}
        )


class LogoutView(APIView):
    """Signs the user out everywhere by invalidating all tokens issued so far."""

    @extend_schema(tags=["Auth"], request=None, responses={204: None})
    def post(self, request):
        bump_token_version(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(tags=["Auth"], responses={200: UserSerializer})
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class PasswordResetRequestView(GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [FailOpenScopedRateThrottle]
    throttle_scope = "password_reset"
    serializer_class = PasswordResetRequestSerializer

    @extend_schema(tags=["Auth"], responses={200: DetailSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_password_reset(serializer.validated_data["email"])
        return Response({"detail": GENERIC_RESET_MESSAGE})


class PasswordResetConfirmView(GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [FailOpenScopedRateThrottle]
    throttle_scope = "password_reset_confirm"
    serializer_class = PasswordResetConfirmSerializer

    @extend_schema(tags=["Auth"], responses={200: DetailSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        confirm_password_reset(**serializer.validated_data)
        return Response({"detail": "Your password has been reset. Please log in."})


class EmailVerifyView(GenericAPIView):
    """Confirm the 6-digit code that was emailed after registration."""

    throttle_classes = [FailOpenScopedRateThrottle]
    throttle_scope = "email_verify"
    serializer_class = EmailVerifySerializer

    @extend_schema(tags=["Auth"], responses={200: UserSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = verify_email(request.user, serializer.validated_data["code"])
        return Response(UserSerializer(user).data)


class EmailResendView(GenericAPIView):
    """Send a new verification code (at most one per minute)."""

    throttle_classes = [FailOpenScopedRateThrottle]
    throttle_scope = "email_resend"
    serializer_class = DetailSerializer

    @extend_schema(tags=["Auth"], request=None, responses={200: DetailSerializer})
    def post(self, request):
        resend_email_verification(request.user)
        return Response({"detail": "A new verification code has been sent."})


class NotificationSettingsView(RetrieveUpdateAPIView):
    """Turn notification emails on or off. Reset and verification codes are always sent."""

    serializer_class = NotificationSettingsSerializer
    http_method_names = ["get", "patch", "head", "options"]

    @extend_schema(tags=["Notifications"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(tags=["Notifications"])
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    def get_object(self):
        return self.request.user
