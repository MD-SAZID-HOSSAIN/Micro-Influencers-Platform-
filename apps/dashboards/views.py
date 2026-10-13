from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.campaigns.discovery import followers_by_platform
from apps.core.permissions import IsCreator

from .serializers import CreatorDashboardSerializer
from .services import creator_dashboard


class CreatorDashboardView(APIView):
    """The creator's home: profile, connection, open campaigns, applications and performance."""

    permission_classes = [IsCreator]

    @extend_schema(tags=["Dashboards"], responses={200: CreatorDashboardSerializer})
    def get(self, request):
        context = {
            "request": request,
            "followers_by_platform": followers_by_platform(request.user),
        }
        return Response(CreatorDashboardSerializer(creator_dashboard(request.user), context=context).data)
