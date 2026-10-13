from drf_spectacular.utils import extend_schema
from rest_framework.generics import RetrieveAPIView, RetrieveUpdateAPIView

from apps.core.permissions import IsBrand, IsCreator

from .models import BrandProfile
from .serializers import BrandProfileSerializer, CreatorProfileSerializer
from .services import get_or_create_profile


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
