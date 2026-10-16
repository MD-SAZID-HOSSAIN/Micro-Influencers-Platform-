import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import (
    DestroyAPIView,
    GenericAPIView,
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateAPIView,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsBrand, IsCreator

from .models import BrandProfile, PortfolioItem
from .serializers import (
    BrandProfileSerializer,
    CreatorProfileSerializer,
    PortfolioItemSerializer,
)
from .services import add_portfolio_item, get_or_create_profile


@extend_schema(tags=["Profiles"], responses={200: CreatorProfileSerializer})
class CreatorPhotoUploadView(GenericAPIView):
    """Upload or remove a profile picture for the logged-in creator."""

    permission_classes = [IsCreator]
    serializer_class = CreatorProfileSerializer
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file = request.FILES.get("photo") or request.FILES.get("file")
        if not file:
            return Response(
                {"error": {"code": "missing_file", "message": "No image file provided.", "details": None}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if file.size > 5 * 1024 * 1024:
            return Response(
                {"error": {"code": "file_too_large", "message": "Image must be under 5 MB.", "details": None}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ext = Path(file.name).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
            return Response(
                {"error": {"code": "invalid_extension", "message": "Only JPG, PNG, WEBP, or GIF are allowed.", "details": None}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        filename = f"avatars/{uuid.uuid4().hex[:12]}_{slugify(Path(file.name).stem)}{ext}"
        saved_path = default_storage.save(filename, file)
        url = request.build_absolute_uri(f"{settings.MEDIA_URL}{saved_path}")

        profile = get_or_create_profile(request.user)
        profile.photo_url = url
        profile.save(update_fields=["photo_url", "updated_at"])

        return Response(CreatorProfileSerializer(profile).data, status=status.HTTP_200_OK)

    def delete(self, request):
        profile = get_or_create_profile(request.user)
        profile.photo_url = None
        profile.save(update_fields=["photo_url", "updated_at"])
        return Response(CreatorProfileSerializer(profile).data, status=status.HTTP_200_OK)


@extend_schema(tags=["Profiles"], responses={200: BrandProfileSerializer})
class BrandLogoUploadView(GenericAPIView):
    """Upload or remove a company logo for the logged-in brand."""

    permission_classes = [IsBrand]
    serializer_class = BrandProfileSerializer
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file = request.FILES.get("logo") or request.FILES.get("file")
        if not file:
            return Response(
                {"error": {"code": "missing_file", "message": "No logo file provided.", "details": None}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if file.size > 5 * 1024 * 1024:
            return Response(
                {"error": {"code": "file_too_large", "message": "Logo must be under 5 MB.", "details": None}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ext = Path(file.name).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"]:
            return Response(
                {"error": {"code": "invalid_extension", "message": "Only JPG, PNG, WEBP, GIF, or SVG are allowed.", "details": None}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        filename = f"logos/{uuid.uuid4().hex[:12]}_{slugify(Path(file.name).stem)}{ext}"
        saved_path = default_storage.save(filename, file)
        url = request.build_absolute_uri(f"{settings.MEDIA_URL}{saved_path}")

        profile = get_or_create_profile(request.user)
        profile.logo_url = url
        profile.save(update_fields=["logo_url", "updated_at"])

        return Response(BrandProfileSerializer(profile).data, status=status.HTTP_200_OK)

    def delete(self, request):
        profile = get_or_create_profile(request.user)
        profile.logo_url = None
        profile.save(update_fields=["logo_url", "updated_at"])
        return Response(BrandProfileSerializer(profile).data, status=status.HTTP_200_OK)


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
