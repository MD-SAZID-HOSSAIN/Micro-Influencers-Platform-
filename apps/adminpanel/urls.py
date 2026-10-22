from django.urls import path

from .views import (
    AdminActionLogView,
    AdminApproveBrandPlatformView,
    AdminApproveStatsView,
    AdminBrandPlatformListView,
    AdminCampaignListView,
    AdminCloseCampaignView,
    AdminLoginView,
    AdminOverviewView,
    AdminPlatformStatsListView,
    AdminReactivateUserView,
    AdminRejectBrandPlatformView,
    AdminRejectStatsView,
    AdminReviewDetailView,
    AdminReviewListView,
    AdminSuspendUserView,
    AdminUserDetailView,
    AdminUserListView,
)

urlpatterns = [
    path("admin/auth/login/", AdminLoginView.as_view(), name="admin-login"),
    path("admin/users/", AdminUserListView.as_view(), name="admin-users"),
    path("admin/users/<int:pk>/", AdminUserDetailView.as_view(), name="admin-user"),
    path("admin/users/<int:pk>/suspend/", AdminSuspendUserView.as_view(), name="admin-user-suspend"),
    path(
        "admin/users/<int:pk>/reactivate/", AdminReactivateUserView.as_view(), name="admin-user-reactivate"
    ),
    path("admin/campaigns/", AdminCampaignListView.as_view(), name="admin-campaigns"),
    path("admin/campaigns/<int:pk>/close/", AdminCloseCampaignView.as_view(), name="admin-campaign-close"),
    path("admin/reviews/", AdminReviewListView.as_view(), name="admin-reviews"),
    path("admin/reviews/<int:pk>/", AdminReviewDetailView.as_view(), name="admin-review"),
    path("admin/platform-stats/", AdminPlatformStatsListView.as_view(), name="admin-platform-stats"),
    path("admin/platform-stats/<int:pk>/approve/", AdminApproveStatsView.as_view(), name="admin-stats-approve"),
    path("admin/platform-stats/<int:pk>/reject/", AdminRejectStatsView.as_view(), name="admin-stats-reject"),
    path("admin/brand-platforms/", AdminBrandPlatformListView.as_view(), name="admin-brand-platforms"),
    path(
        "admin/brand-platforms/<int:pk>/approve/", AdminApproveBrandPlatformView.as_view(), name="admin-brand-platform-approve"
    ),
    path(
        "admin/brand-platforms/<int:pk>/reject/", AdminRejectBrandPlatformView.as_view(), name="admin-brand-platform-reject"
    ),
    path("admin/actions/", AdminActionLogView.as_view(), name="admin-actions"),
    path("admin/overview/", AdminOverviewView.as_view(), name="admin-overview"),
]
