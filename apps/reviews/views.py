from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.response import Response

from apps.accounts.models import Role, User
from apps.core.permissions import IsBrand

from .models import Review
from .serializers import ReviewCreateSerializer, ReviewSerializer
from .services import create_review


class CreateReviewView(GenericAPIView):
    """Rate a creator after a Completed collaboration. One review per collaboration; no edits."""

    permission_classes = [IsBrand]
    serializer_class = ReviewCreateSerializer
    http_method_names = ["post", "options"]

    @extend_schema(tags=["Reviews"], responses={201: ReviewSerializer})
    def post(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = create_review(brand=request.user, proposal_id=pk, **serializer.validated_data)
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Reviews"])
class CreatorReviewsView(ListAPIView):
    """The reviews a creator has received, newest first (for logged-in brands)."""

    permission_classes = [IsBrand]
    serializer_class = ReviewSerializer

    def get_queryset(self):
        creator = get_object_or_404(User, pk=self.kwargs["user_id"], role=Role.CREATOR, is_active=True)
        return Review.objects.filter(creator=creator).select_related(
            "brand__brand_profile", "proposal__campaign"
        )
