"""Throwaway URLconf exercising the shared API plumbing (errors, pagination)."""
from django.http import Http404
from django.urls import path
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import Conflict
from apps.core.pagination import StandardPagination


class Open(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []


class ConflictView(Open):
    def get(self, request):
        raise Conflict("Already exists.")


class NotFoundView(Open):
    def get(self, request):
        raise Http404


class NameSerializer(serializers.Serializer):
    name = serializers.CharField()


class ValidationView(Open):
    def post(self, request):
        serializer = NameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class NumbersView(Open):
    def get(self, request):
        paginator = StandardPagination()
        page = paginator.paginate_queryset(list(range(120)), request)
        return paginator.get_paginated_response(page)


class NeedsAuthView(APIView):
    """Keeps project defaults so the 401 body shape can be checked."""

    def get(self, request):
        return Response({})


urlpatterns = [
    path("conflict/", ConflictView.as_view()),
    path("missing/", NotFoundView.as_view()),
    path("validate/", ValidationView.as_view()),
    path("numbers/", NumbersView.as_view()),
    path("needs-auth/", NeedsAuthView.as_view()),
]
