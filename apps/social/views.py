from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.choices import Platform
from apps.core.permissions import IsCreator

from .models import PlatformStats
from .serializers import PlatformStatsSerializer
from .services import request_manual_refresh, set_manual_stats


@extend_schema(tags=["Social"])
class MyStatsListView(ListAPIView):
    permission_classes = [IsCreator]
    serializer_class = PlatformStatsSerializer
    pagination_class = None

    def get_queryset(self):
        return PlatformStats.objects.filter(creator=self.request.user)


class ManualStatsView(APIView):
    """Enter Unverified stats by hand for a platform (the fallback to account connection)."""

    permission_classes = [IsCreator]

    @extend_schema(
        tags=["Social"], request=PlatformStatsSerializer, responses={200: PlatformStatsSerializer}
    )
    def put(self, request, platform):
        if platform not in Platform.values:
            raise Http404
        serializer = PlatformStatsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stats = set_manual_stats(creator=request.user, platform=platform, **serializer.validated_data)
        return Response(PlatformStatsSerializer(stats).data)


class YouTubeRefreshView(APIView):
    """Ask for an immediate stats refresh (rate limited by a cooldown)."""

    permission_classes = [IsCreator]

    @extend_schema(tags=["Social"], request=None, responses={202: None})
    def post(self, request):
        request_manual_refresh(request.user)
        return Response({"detail": "Refresh scheduled."}, status=status.HTTP_202_ACCEPTED)
