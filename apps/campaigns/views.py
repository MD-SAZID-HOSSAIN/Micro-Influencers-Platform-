from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework.generics import ListAPIView, RetrieveAPIView

from apps.core.permissions import IsBrand, IsCreator

from .analytics import campaign_metrics, record_campaign_view
from django.conf import settings
from .discovery import CampaignFilterSerializer, discovery_queryset, followers_by_platform
from apps.core.uploads import MediaTooLarge

from .media import add_media, remove_media
from .models import Campaign
from .serializers import (
    BrandCampaignListFilterSerializer,
    CampaignCardSerializer,
    CampaignMediaSerializer,
    CampaignMetricsSerializer,
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
        return Campaign.objects.filter(brand=self.request.user).prefetch_related("media")


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
        done = self.transition(campaign)
        return Response(CampaignSerializer(done, context={"request": request}).data)


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
    """Full details of a published or closed campaign. Drafts and suspended brands' campaigns are never visible."""

    serializer_class = CampaignDetailSerializer

    def get_queryset(self):
        return Campaign.objects.filter(
            status__in=[Campaign.Status.PUBLISHED, Campaign.Status.CLOSED],
            brand__is_active=True,
        ).select_related("brand__brand_profile").prefetch_related("media")

    def retrieve(self, request, *args, **kwargs):
        campaign = self.get_object()
        record_campaign_view(campaign, request.user)  # feeds the brand's analytics
        return Response(self.get_serializer(campaign).data)


class CampaignAnalyticsView(APIView):
    """Proposal metrics for one of the brand's campaigns (another brand's campaign is a 404)."""

    permission_classes = [IsBrand]

    @extend_schema(tags=["Campaigns"], responses={200: CampaignMetricsSerializer})
    def get(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, brand=request.user)
        return Response(CampaignMetricsSerializer(campaign_metrics(campaign)).data)


class CampaignMediaCreateView(APIView):
    """Attach a photo or video to one of the brand's Draft campaigns (2 photos, or 1 video)."""

    permission_classes = [IsBrand]
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=["Campaigns"],
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
                "required": ["file"],
            }
        },
        responses={201: CampaignMediaSerializer},
    )
    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, brand=request.user)
        # Refuse an obviously oversized body before reading it all (the exact limit is checked per type).
        declared = int(request.META.get("CONTENT_LENGTH") or 0)
        if declared > settings.MEDIA_MAX_VIDEO_BYTES + 1024 * 1024:
            raise MediaTooLarge()
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": ["Choose a photo or a video to upload."]})
        media = add_media(campaign, upload)
        return Response(
            CampaignMediaSerializer(media, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class CampaignMediaDeleteView(APIView):
    """Remove one photo or video from a Draft campaign."""

    permission_classes = [IsBrand]

    @extend_schema(tags=["Campaigns"], responses={204: None})
    def delete(self, request, pk, media_id):
        campaign = get_object_or_404(Campaign, pk=pk, brand=request.user)
        if not remove_media(campaign, media_id):
            raise NotFound("Media not found.")
        return Response(status=status.HTTP_204_NO_CONTENT)
