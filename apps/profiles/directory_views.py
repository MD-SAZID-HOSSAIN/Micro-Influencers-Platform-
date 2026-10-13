from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView, RetrieveAPIView

from apps.core.permissions import IsBrand

from .filters import DirectoryFilterSerializer, directory_queryset
from .models import CreatorProfile
from .serializers import CreatorCardSerializer, CreatorDetailSerializer


@extend_schema(tags=["Discovery"], parameters=[DirectoryFilterSerializer])
class CreatorDirectoryView(ListAPIView):
    """Brand-facing creator directory: search, filter, sort, paginate."""

    permission_classes = [IsBrand]
    serializer_class = CreatorCardSerializer

    def get_queryset(self):
        params = DirectoryFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        return directory_queryset(params.validated_data)


@extend_schema(tags=["Discovery"])
class CreatorDetailView(RetrieveAPIView):
    """The full profile of one creator, for logged-in brands."""

    permission_classes = [IsBrand]
    serializer_class = CreatorDetailSerializer
    lookup_field = "user_id"
    lookup_url_kwarg = "user_id"

    def get_queryset(self):
        return (
            CreatorProfile.objects.filter(user__is_active=True)
            .select_related("user")
            .prefetch_related("user__platform_stats", "user__portfolio_items")
        )
