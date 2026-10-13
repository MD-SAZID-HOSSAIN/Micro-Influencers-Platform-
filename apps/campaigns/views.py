from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework.generics import ListAPIView, RetrieveAPIView

from apps.core.permissions import IsBrand, IsCreator

from .discovery import CampaignFilterSerializer, discovery_queryset, followers_by_platform
from .models import Campaign
from .serializers import (
    BrandCampaignListFilterSerializer,
    CampaignCardSerializer,
    CampaignDetailSerializer,
    CampaignSerializer,
)
from .services import (
    CampaignNotEditable,
    close_campaign,
    delete_campaign,
    publish_campaign,
    update_campaign,
)


class _BrandCampaignMixin:
    """Every brand endpoint only ever sees that brand's own campaigns (others are a 404)."""

    permission_classes = [IsBrand]
    serializer_class = CampaignSerializer

    def get_queryset(self):
        return Campaign.objects.filter(brand=self.request.user)


@extend_schema(tags=["Campaigns"], parameters=[BrandCampaignListFilterSerializer])
class BrandCampaignListCreateView(_BrandCampaignMixin, ListCreateAPIView):
    """List the brand's campaigns (newest first) or create a new Draft."""

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.method == "GET":
            params = BrandCampaignListFilterSerializer(data=self.request.query_params)
            params.is_valid(raise_exception=True)
            if wanted := params.validated_data.get("status"):
                queryset = queryset.filter(status=wanted)
        return queryset

    def perform_create(self, serializer):
        serializer.save(brand=self.request.user)


@extend_schema(tags=["Campaigns"])
class BrandCampaignDetailView(_BrandCampaignMixin, RetrieveUpdateDestroyAPIView):
    """Read a campaign; edit or delete it while it is still a Draft."""

    http_method_names = ["get", "patch", "delete", "head", "options"]

    def update(self, request, *args, **kwargs):
        campaign = self.get_object()
        if campaign.status != Campaign.Status.DRAFT:
            raise CampaignNotEditable()  # reported before any validation error
        serializer = self.get_serializer(campaign, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = update_campaign(campaign, serializer.validated_data)
        return Response(self.get_serializer(updated).data)

    def destroy(self, request, *args, **kwargs):
        delete_campaign(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)


class _TransitionView(APIView):
    permission_classes = [IsBrand]

    def transition(self, campaign):
        raise NotImplementedError

    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, brand=request.user)
        return Response(CampaignSerializer(self.transition(campaign)).data)


class PublishCampaignView(_TransitionView):
    @extend_schema(tags=["Campaigns"], request=None, responses={200: CampaignSerializer})
    def post(self, request, pk):
        return super().post(request, pk)

    def transition(self, campaign):
        return publish_campaign(campaign)


class CloseCampaignView(_TransitionView):
    @extend_schema(tags=["Campaigns"], request=None, responses={200: CampaignSerializer})
    def post(self, request, pk):
        return super().post(request, pk)

    def transition(self, campaign):
        return close_campaign(campaign)


class _CreatorCampaignMixin:
    permission_classes = [IsCreator]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["followers_by_platform"] = followers_by_platform(self.request.user)
        return context


@extend_schema(tags=["Discovery"], parameters=[CampaignFilterSerializer])
class CreatorCampaignListView(_CreatorCampaignMixin, ListAPIView):
    """Open (published, not past deadline) campaigns for logged-in creators."""

    serializer_class = CampaignCardSerializer

    def get_queryset(self):
        params = CampaignFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        return discovery_queryset(params.validated_data)


@extend_schema(tags=["Discovery"])
class CreatorCampaignDetailView(_CreatorCampaignMixin, RetrieveAPIView):
    """Full details of a published or closed campaign. Drafts are never visible."""

    serializer_class = CampaignDetailSerializer

    def get_queryset(self):
        return Campaign.objects.filter(
            status__in=[Campaign.Status.PUBLISHED, Campaign.Status.CLOSED]
        ).select_related("brand__brand_profile")
