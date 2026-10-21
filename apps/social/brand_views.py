from django.conf import settings
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.choices import Platform
from apps.core.permissions import IsBrand
from apps.core.throttling import FailOpenScopedRateThrottle

from . import brand_accounts
from .models import BrandSocialAccount
from .serializers import (
    AuthorizationUrlSerializer,
    BrandSocialAccountSerializer,
    BrandSocialLinkSerializer,
    CompleteConnectSerializer,
)
from .services import start_connect


def _accounts(brand) -> list[dict]:
    return BrandSocialAccountSerializer(BrandSocialAccount.objects.filter(brand=brand), many=True).data


@extend_schema(tags=["Social"])
class BrandSocialListView(APIView):
    """The platforms the signed-in brand has connected. One, of any kind, completes its verification."""

    permission_classes = [IsBrand]

    @extend_schema(responses={200: BrandSocialAccountSerializer(many=True)})
    def get(self, request):
        return Response(_accounts(request.user))


class BrandSocialAccountView(APIView):
    """Add a typed link (Instagram, TikTok, Facebook) or remove any connected platform."""

    permission_classes = [IsBrand]

    @staticmethod
    def _platform(platform: str) -> str:
        if platform not in Platform.values:
            raise Http404
        return platform

    @extend_schema(
        tags=["Social"], request=BrandSocialLinkSerializer, responses={200: BrandSocialAccountSerializer}
    )
    def put(self, request, platform):
        platform = self._platform(platform)
        serializer = BrandSocialLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = brand_accounts.connect_typed_platform(
            brand=request.user, platform=platform, handle_url=serializer.validated_data["handle_url"]
        )
        return Response(BrandSocialAccountSerializer(account).data)

    @extend_schema(tags=["Social"], responses={204: None})
    def delete(self, request, platform):
        brand_accounts.remove_platform(brand=request.user, platform=self._platform(platform))
        return Response(status=status.HTTP_204_NO_CONTENT)


class BrandYouTubeConnectView(APIView):
    """Start the Google sign-in for a brand: returns the Google URL to send the browser to."""

    permission_classes = [IsBrand]

    @extend_schema(tags=["Social"], responses={200: AuthorizationUrlSerializer})
    def get(self, request):
        if not settings.GOOGLE_CLIENT_ID:
            return Response({"authorization_url": ""})
        return Response({"authorization_url": start_connect(request.user)})


class BrandYouTubeCompleteView(GenericAPIView):
    """Finish connecting YouTube for a brand. Send back the ``state`` and ``code`` the callback redirect carried."""

    permission_classes = [IsBrand]
    throttle_classes = [FailOpenScopedRateThrottle]
    throttle_scope = "youtube_complete"
    serializer_class = CompleteConnectSerializer

    @extend_schema(tags=["Social"], responses={200: BrandSocialAccountSerializer(many=True)})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        brand_accounts.complete_brand_youtube(brand=request.user, **serializer.validated_data)
        return Response(_accounts(request.user))
