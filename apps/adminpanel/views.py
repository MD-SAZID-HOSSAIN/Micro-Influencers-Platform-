from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role, User
from apps.accounts.serializers import LoginResponseSerializer, LoginSerializer, UserSerializer
from apps.accounts.services import InvalidCredentials, authenticate_login, issue_access_token
from apps.core.throttling import FailOpenScopedRateThrottle
from apps.core.permissions import IsAdminRole
from apps.social.models import BrandSocialAccount, PlatformStats

from .models import AdminActionLog
from .serializers import (
    AdminActionLogSerializer,
    AdminBrandPlatformSerializer,
    AdminCampaignSerializer,
    AdminPlatformStatsSerializer,
    AdminStatsFilterSerializer,
    AdminUserFilterSerializer,
    AdminUserSerializer,
    OptionalReasonSerializer,
    OverviewSerializer,
    ReasonSerializer,
)
from .services import (
    approve_brand_platform,
    approve_platform_stats,
    close_campaign_as_admin,
    delete_user,
    overview,
    reactivate_user,
    reject_brand_platform,
    reject_platform_stats,
    remove_review,
    suspend_user,
)


class AdminLoginView(GenericAPIView):
    """Log in to the admin panel. Only admin accounts are accepted here (and only here)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [FailOpenScopedRateThrottle]
    throttle_scope = "admin_login"
    serializer_class = LoginSerializer

    @extend_schema(tags=["Admin"], responses={200: LoginResponseSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate_login(**serializer.validated_data)
        if user.role != Role.ADMIN:
            raise InvalidCredentials()  # same answer as a wrong password: no hint about the account
        return Response({"access": issue_access_token(user), "user": UserSerializer(user).data})


@extend_schema(tags=["Admin"], parameters=[AdminUserFilterSerializer])
class AdminUserListView(ListAPIView):
    """Search and filter every account."""

    permission_classes = [IsAdminRole]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        params = AdminUserFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        users = User.objects.order_by("-date_joined", "-id")
        if q := params.validated_data.get("q"):
            users = users.filter(
                Q(full_name__icontains=q) | Q(email__icontains=q) | Q(username__icontains=q)
            )
        if role := params.validated_data.get("role"):
            users = users.filter(role=role)
        if wanted := params.validated_data.get("status"):
            users = users.filter(is_active=(wanted == "active"))
        return users


class _ReasonedAction(GenericAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = ReasonSerializer

    def reason(self, request) -> str:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data["reason"]


class AdminSuspendUserView(_ReasonedAction):
    @extend_schema(tags=["Admin"], responses={200: AdminUserSerializer})
    def post(self, request, pk):
        user = suspend_user(admin=request.user, user_id=pk, reason=self.reason(request))
        return Response(AdminUserSerializer(user).data)


class AdminReactivateUserView(_ReasonedAction):
    @extend_schema(tags=["Admin"], responses={200: AdminUserSerializer})
    def post(self, request, pk):
        user = reactivate_user(admin=request.user, user_id=pk, reason=self.reason(request))
        return Response(AdminUserSerializer(user).data)


class AdminUserDetailView(_ReasonedAction):
    """DELETE removes the account and its data. The JSON body must contain a ``reason``."""

    http_method_names = ["delete", "options"]

    @extend_schema(tags=["Admin"], request=ReasonSerializer, responses={204: None})
    def delete(self, request, pk):
        delete_user(admin=request.user, user_id=pk, reason=self.reason(request))
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminCloseCampaignView(_ReasonedAction):
    @extend_schema(tags=["Admin"], responses={200: AdminCampaignSerializer})
    def post(self, request, pk):
        campaign = close_campaign_as_admin(admin=request.user, campaign_id=pk, reason=self.reason(request))
        return Response(AdminCampaignSerializer(campaign).data)


class AdminReviewDetailView(_ReasonedAction):
    """DELETE removes an inappropriate review and recalculates the creator's rating."""

    http_method_names = ["delete", "options"]

    @extend_schema(tags=["Admin"], request=ReasonSerializer, responses={204: None})
    def delete(self, request, pk):
        remove_review(admin=request.user, review_id=pk, reason=self.reason(request))
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Admin"], parameters=[AdminStatsFilterSerializer])
class AdminPlatformStatsListView(ListAPIView):
    """Instagram, TikTok and Facebook numbers that creators typed. Oldest first."""

    permission_classes = [IsAdminRole]
    serializer_class = AdminPlatformStatsSerializer

    def get_queryset(self):
        params = AdminStatsFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        return (
            PlatformStats.objects.exclude(platform="youtube")
            .filter(review_status=params.validated_data["status"])
            .select_related("creator")
            .order_by("updated_at", "id")
        )


class AdminApproveStatsView(GenericAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = OptionalReasonSerializer

    @extend_schema(tags=["Admin"], responses={200: AdminPlatformStatsSerializer})
    def post(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stats = approve_platform_stats(
            admin=request.user, stats_id=pk, reason=serializer.validated_data.get("reason", "")
        )
        return Response(AdminPlatformStatsSerializer(stats).data)


class AdminRejectStatsView(_ReasonedAction):
    @extend_schema(tags=["Admin"], responses={200: AdminPlatformStatsSerializer})
    def post(self, request, pk):
        stats = reject_platform_stats(admin=request.user, stats_id=pk, reason=self.reason(request))
        return Response(AdminPlatformStatsSerializer(stats).data)


@extend_schema(tags=["Admin"], parameters=[AdminStatsFilterSerializer])
class AdminBrandPlatformListView(ListAPIView):
    """Instagram, TikTok and Facebook links that brands typed. Oldest first."""

    permission_classes = [IsAdminRole]
    serializer_class = AdminBrandPlatformSerializer

    def get_queryset(self):
        params = AdminStatsFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        return (
            BrandSocialAccount.objects.exclude(platform="youtube")
            .filter(review_status=params.validated_data["status"])
            .select_related("brand")
            .order_by("connected_at", "id")
        )


class AdminApproveBrandPlatformView(GenericAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = OptionalReasonSerializer

    @extend_schema(tags=["Admin"], responses={200: AdminBrandPlatformSerializer})
    def post(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = approve_brand_platform(
            admin=request.user, account_id=pk, reason=serializer.validated_data.get("reason", "")
        )
        return Response(AdminBrandPlatformSerializer(account).data)


class AdminRejectBrandPlatformView(_ReasonedAction):
    @extend_schema(tags=["Admin"], responses={200: AdminBrandPlatformSerializer})
    def post(self, request, pk):
        account = reject_brand_platform(admin=request.user, account_id=pk, reason=self.reason(request))
        return Response(AdminBrandPlatformSerializer(account).data)


@extend_schema(tags=["Admin"])
class AdminActionLogView(ListAPIView):
    """The audit trail of everything admins have done, newest first."""

    permission_classes = [IsAdminRole]
    serializer_class = AdminActionLogSerializer
    queryset = AdminActionLog.objects.all()


class AdminOverviewView(APIView):
    permission_classes = [IsAdminRole]

    @extend_schema(tags=["Admin"], responses={200: OverviewSerializer})
    def get(self, request):
        return Response(overview())
