from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.choices import Platform
from apps.core.permissions import IsBrand

from . import brand_accounts
from .models import BrandSocialAccount
from .serializers import BrandSocialAccountSerializer, BrandSocialLinkSerializer


def _accounts(brand) -> list[dict]:
    # YouTube rows from before brands stopped verifying with it are kept but never shown or counted.
    rows = BrandSocialAccount.objects.filter(brand=brand).exclude(platform="youtube")
    return BrandSocialAccountSerializer(rows, many=True).data


@extend_schema(tags=["Social"])
class BrandSocialListView(APIView):
    """The platforms the signed-in brand has added. One approved link completes its verification."""

    permission_classes = [IsBrand]

    @extend_schema(responses={200: BrandSocialAccountSerializer(many=True)})
    def get(self, request):
        return Response(_accounts(request.user))


class BrandSocialAccountView(APIView):
    """Add a typed link (Instagram, TikTok, Facebook) or remove a connected platform."""

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
