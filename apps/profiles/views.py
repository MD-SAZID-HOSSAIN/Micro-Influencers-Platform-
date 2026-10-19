from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.generics import (
    DestroyAPIView,
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateAPIView,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsBrand, IsCreator
from apps.core.uploads import MediaTooLarge

from .images import clear_picture, set_picture
from .models import BrandProfile, PortfolioItem
from .serializers import (
    BrandProfileSerializer,
    CreatorProfileSerializer,
    PortfolioItemSerializer,
)
from .services import add_portfolio_item, get_or_create_profile


@extend_schema(tags=["Profiles"])
class CreatorMeView(RetrieveUpdateAPIView):
    """The signed-in creator's own profile."""

    permission_classes = [IsCreator]
    serializer_class = CreatorProfileSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return get_or_create_profile(self.request.user)


@extend_schema(tags=["Profiles"])
class BrandMeView(RetrieveUpdateAPIView):
    """The signed-in brand's own company profile."""

    permission_classes = [IsBrand]
    serializer_class = BrandProfileSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return get_or_create_profile(self.request.user)


@extend_schema(tags=["Profiles"])
class BrandDetailView(RetrieveAPIView):
    """A brand's public company profile, visible to logged-in creators."""

    permission_classes = [IsCreator]
    serializer_class = BrandProfileSerializer
    queryset = BrandProfile.objects.select_related("user")
    lookup_field = "user_id"
    lookup_url_kwarg = "user_id"


@extend_schema(tags=["Profiles"])
class PortfolioListCreateView(ListCreateAPIView):
    """The signed-in creator's portfolio links (maximum 10)."""

    permission_classes = [IsCreator]
    serializer_class = PortfolioItemSerializer
    pagination_class = None

    def get_queryset(self):
        return PortfolioItem.objects.filter(creator=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = add_portfolio_item(creator=request.user, **serializer.validated_data)
        return Response(self.get_serializer(item).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Profiles"])
class PortfolioDeleteView(DestroyAPIView):
    permission_classes = [IsCreator]
    serializer_class = PortfolioItemSerializer

    def get_queryset(self):
        return PortfolioItem.objects.filter(creator=self.request.user)


_UPLOAD_BODY = {
    "multipart/form-data": {
        "type": "object",
        "properties": {"file": {"type": "string", "format": "binary"}},
        "required": ["file"],
    }
}


class _ProfilePictureView(APIView):
    """Upload (PUT) or remove (DELETE) the signed-in user's profile picture; both return the profile."""

    parser_classes = [MultiPartParser]
    serializer_class = None  # the profile serializer used for the response

    def _upload(self, request):
        declared = int(request.META.get("CONTENT_LENGTH") or 0)
        if declared > settings.MEDIA_MAX_PHOTO_BYTES + 1024 * 1024:
            raise MediaTooLarge()  # refuse an oversized body before reading it all
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": ["Choose a photo to upload."]})
        return upload

    def put(self, request):
        profile = set_picture(get_or_create_profile(request.user), self._upload(request))
        return Response(self.serializer_class(profile).data)

    def delete(self, request):
        profile = clear_picture(get_or_create_profile(request.user))
        return Response(self.serializer_class(profile).data)


class CreatorPhotoView(_ProfilePictureView):
    """The creator's profile photo (JPG, PNG or WebP, up to 5 MB)."""

    permission_classes = [IsCreator]
    serializer_class = CreatorProfileSerializer

    @extend_schema(tags=["Profiles"], request=_UPLOAD_BODY, responses={200: CreatorProfileSerializer})
    def put(self, request):
        return super().put(request)

    @extend_schema(tags=["Profiles"], responses={200: CreatorProfileSerializer})
    def delete(self, request):
        return super().delete(request)


class BrandLogoView(_ProfilePictureView):
    """The brand's logo (JPG, PNG or WebP, up to 5 MB)."""

    permission_classes = [IsBrand]
    serializer_class = BrandProfileSerializer

    @extend_schema(tags=["Profiles"], request=_UPLOAD_BODY, responses={200: BrandProfileSerializer})
    def put(self, request):
        return super().put(request)

    @extend_schema(tags=["Profiles"], responses={200: BrandProfileSerializer})
    def delete(self, request):
        return super().delete(request)
