from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView, ListAPIView, ListCreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.campaigns.models import Campaign
from apps.core.pagination import StandardPagination
from apps.core.permissions import IsBrand, IsCreator
from apps.social.queries import annotate_primary_stats

from .apply_state import accepted_count
from .deliverable_stats import content_performance
from .deliverables import (
    complete_proposal,
    delete_deliverable,
    list_deliverables,
    submit_deliverable,
    update_deliverable,
)
from .models import Proposal
from .serializers import (
    BrandProposalSerializer,
    CampaignDeliverablesRowSerializer,
    CompletionResultSerializer,
    ContentPerformanceRowSerializer,
    DeliverableSerializer,
    MyProposalSerializer,
    ProposalActionResultSerializer,
    ProposalSerializer,
    ProposalSubmitSerializer,
    WithdrawSerializer,
)
from .services import (
    accept_proposal,
    reject_proposal,
    shortlist_proposal,
    submit_proposal,
    withdraw_proposal,
)


class SubmitProposalView(GenericAPIView):
    """Apply to a published campaign. Proposals cannot be edited afterwards."""

    permission_classes = [IsCreator]
    serializer_class = ProposalSubmitSerializer
    http_method_names = ["post", "options"]

    @extend_schema(tags=["Proposals"], responses={201: ProposalSerializer})
    def post(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proposal = submit_proposal(
            creator=request.user, campaign_id=pk, **serializer.validated_data
        )
        return Response(ProposalSerializer(proposal).data, status=status.HTTP_201_CREATED)


class WithdrawProposalView(GenericAPIView):
    """Withdraw an active proposal (an Accepted one needs a short reason)."""

    permission_classes = [IsCreator]
    serializer_class = WithdrawSerializer
    http_method_names = ["post", "options"]

    @extend_schema(tags=["Proposals"], responses={200: ProposalSerializer})
    def post(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proposal = withdraw_proposal(
            creator=request.user, proposal_id=pk, reason=serializer.validated_data.get("reason")
        )
        return Response(ProposalSerializer(proposal).data)


class ProposalStatusFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Proposal.Status.choices, required=False)


class BrandProposalPagination(StandardPagination):
    """Standard pagination plus the campaign's accepted-vs-needed counter."""

    def paginate_queryset(self, queryset, request, view=None):
        self.view = view
        return super().paginate_queryset(queryset, request, view)

    def get_paginated_response(self, data):
        campaign = self.view.campaign
        response = super().get_paginated_response(data)
        response.data["accepted_count"] = accepted_count(campaign)
        response.data["creators_needed"] = campaign.creators_needed
        return response

    def get_paginated_response_schema(self, schema):
        schema = super().get_paginated_response_schema(schema)
        schema["properties"]["accepted_count"] = {"type": "integer", "example": 2}
        schema["properties"]["creators_needed"] = {"type": "integer", "example": 3}
        schema["required"] += ["accepted_count", "creators_needed"]
        return schema


@extend_schema(tags=["Proposals"], parameters=[ProposalStatusFilterSerializer])
class BrandProposalListView(ListAPIView):
    """Proposals received for one of the brand's campaigns, newest first.

    Withdrawn proposals are hidden unless ``status=withdrawn`` is requested.
    """

    permission_classes = [IsBrand]
    serializer_class = BrandProposalSerializer
    pagination_class = BrandProposalPagination

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # Another brand's campaign is a 404, never a 403.
        self.campaign = get_object_or_404(Campaign, pk=kwargs["pk"], brand=request.user)

    def get_queryset(self):
        params = ProposalStatusFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        proposals = Proposal.objects.filter(campaign=self.campaign).select_related(
            "creator", "creator__creator_profile"
        )
        if wanted := params.validated_data.get("status"):
            proposals = proposals.filter(status=wanted)
        else:
            proposals = proposals.exclude(status=Proposal.Status.WITHDRAWN)
        return annotate_primary_stats(
            proposals,
            creator_field="creator_id",
            platform_field="creator__creator_profile__primary_platform",
        )


class _ProposalActionView(APIView):
    """Base for the brand's shortlist / accept / reject buttons."""

    permission_classes = [IsBrand]
    http_method_names = ["post", "options"]
    service = None  # a service function: (brand, proposal_id) -> Proposal

    def post(self, request, pk):
        proposal = type(self).service(brand=request.user, proposal_id=pk)
        campaign = proposal.campaign
        return Response(
            {
                "id": proposal.id,
                "status": proposal.status,
                "accepted_count": accepted_count(campaign),
                "creators_needed": campaign.creators_needed,
            }
        )


class ShortlistProposalView(_ProposalActionView):
    service = staticmethod(shortlist_proposal)

    @extend_schema(tags=["Proposals"], request=None, responses={200: ProposalActionResultSerializer})
    def post(self, request, pk):
        return super().post(request, pk)


class AcceptProposalView(_ProposalActionView):
    service = staticmethod(accept_proposal)

    @extend_schema(tags=["Proposals"], request=None, responses={200: ProposalActionResultSerializer})
    def post(self, request, pk):
        return super().post(request, pk)


class RejectProposalView(_ProposalActionView):
    service = staticmethod(reject_proposal)

    @extend_schema(tags=["Proposals"], request=None, responses={200: ProposalActionResultSerializer})
    def post(self, request, pk):
        return super().post(request, pk)


@extend_schema(tags=["Proposals"], parameters=[ProposalStatusFilterSerializer])
class MyProposalListView(ListAPIView):
    """Every campaign the creator applied to, with the status of each proposal (newest first).

    Withdrawn proposals stay as history, and a resubmission is a separate entry.
    """

    permission_classes = [IsCreator]
    serializer_class = MyProposalSerializer
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        params = ProposalStatusFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        proposals = Proposal.objects.filter(creator=self.request.user).select_related(
            "campaign__brand__brand_profile"
        )
        if wanted := params.validated_data.get("status"):
            proposals = proposals.filter(status=wanted)
        return proposals


@extend_schema(tags=["Proposals"])
class DeliverableListCreateView(ListCreateAPIView):
    """The content an accepted creator delivered for a proposal. New ones are accepted until completion."""

    permission_classes = [IsCreator]
    serializer_class = DeliverableSerializer
    pagination_class = None

    def get_queryset(self):
        return list_deliverables(creator=self.request.user, proposal_id=self.kwargs["pk"])

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deliverable = submit_deliverable(
            creator=request.user, proposal_id=kwargs["pk"], **serializer.validated_data
        )
        return Response(self.get_serializer(deliverable).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Proposals"])
class DeliverableDetailView(GenericAPIView):
    """Update or remove one deliverable, until the brand marks the collaboration Completed."""

    permission_classes = [IsCreator]
    serializer_class = DeliverableSerializer
    http_method_names = ["patch", "delete", "options"]

    def patch(self, request, pk, deliverable_id):
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        deliverable = update_deliverable(
            creator=request.user,
            proposal_id=pk,
            deliverable_id=deliverable_id,
            changes=serializer.validated_data,
        )
        return Response(self.get_serializer(deliverable).data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk, deliverable_id):
        delete_deliverable(creator=request.user, proposal_id=pk, deliverable_id=deliverable_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Proposals"], responses={200: CampaignDeliverablesRowSerializer(many=True)})
class CampaignDeliverablesView(ListAPIView):
    """What each accepted creator has delivered, for the owner of the campaign."""

    permission_classes = [IsBrand]
    serializer_class = CampaignDeliverablesRowSerializer
    pagination_class = None

    def get_queryset(self):
        campaign = get_object_or_404(Campaign, pk=self.kwargs["pk"], brand=self.request.user)
        return (
            Proposal.objects.filter(campaign=campaign, status=Proposal.Status.ACCEPTED)
            .select_related("creator")
            .prefetch_related("deliverables")
            .order_by("created_at", "id")
        )


class CompleteProposalView(APIView):
    """Mark an accepted collaboration Completed. Final; unlocks the review."""

    permission_classes = [IsBrand]
    http_method_names = ["post", "options"]

    @extend_schema(tags=["Proposals"], request=None, responses={200: CompletionResultSerializer})
    def post(self, request, pk):
        proposal = complete_proposal(brand=request.user, proposal_id=pk)
        return Response(
            {"id": proposal.id, "status": proposal.status, "completed_at": proposal.completed_at}
        )


class CampaignContentPerformanceView(APIView):
    """Views, likes, comments and engagement per delivered post, from the daily snapshot.

    Opening this never calls YouTube. Figures the platform does not provide are "not_available".
    """

    permission_classes = [IsBrand]

    @extend_schema(tags=["Campaigns"], responses={200: ContentPerformanceRowSerializer(many=True)})
    def get(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, brand=request.user)
        return Response(ContentPerformanceRowSerializer(content_performance(campaign), many=True).data)
