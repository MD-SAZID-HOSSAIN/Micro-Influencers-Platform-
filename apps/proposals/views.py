from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from apps.core.permissions import IsCreator

from .serializers import ProposalSerializer, ProposalSubmitSerializer, WithdrawSerializer
from .services import submit_proposal, withdraw_proposal


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
