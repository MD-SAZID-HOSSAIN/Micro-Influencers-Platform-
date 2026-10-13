from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .serializers import (
    LoginResponseSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .services import authenticate_login, bump_token_version, issue_access_token


class RegisterView(GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"
    serializer_class = LoginSerializer

    @extend_schema(tags=["Auth"], responses={200: LoginResponseSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate_login(**serializer.validated_data)
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
