from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination

from .models import Notification
from .serializers import MarkAllReadResponseSerializer, NotificationSerializer


class NotificationPagination(StandardPagination):
    """Standard pagination plus the user's total unread count (for the nav badge)."""

    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        response.data["unread_count"] = Notification.objects.filter(
            user=self.request.user, is_read=False
        ).count()
        return response

    def get_paginated_response_schema(self, schema):
        schema = super().get_paginated_response_schema(schema)
        schema["properties"]["unread_count"] = {"type": "integer", "example": 3}
        schema["required"].append("unread_count")
        return schema


@extend_schema(tags=["Notifications"])
class NotificationListView(ListAPIView):
    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class MarkReadView(APIView):
    @extend_schema(tags=["Notifications"], request=None, responses={200: NotificationSerializer})
    def post(self, request, pk):
        notification = get_object_or_404(Notification, user=request.user, pk=pk)
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)


class MarkAllReadView(APIView):
    @extend_schema(
        tags=["Notifications"], request=None, responses={200: MarkAllReadResponseSerializer}
    )
    def post(self, request):
        updated = Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True
        )
        return Response({"marked_read": updated})
