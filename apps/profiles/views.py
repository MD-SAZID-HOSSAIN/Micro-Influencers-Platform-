from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import (
    DestroyAPIView,
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateAPIView,
)
from rest_framework.response import Response

from apps.core.permissions import IsBrand, IsCreator

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
