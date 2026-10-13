from django.urls import path

from .views import (
    AdminActionLogView,
    AdminCloseCampaignView,
    AdminLoginView,
    AdminOverviewView,
    AdminReactivateUserView,
    AdminReviewDetailView,
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
    path("admin/campaigns/<int:pk>/close/", AdminCloseCampaignView.as_view(), name="admin-campaign-close"),
    path("admin/reviews/<int:pk>/", AdminReviewDetailView.as_view(), name="admin-review"),
    path("admin/actions/", AdminActionLogView.as_view(), name="admin-actions"),
    path("admin/overview/", AdminOverviewView.as_view(), name="admin-overview"),
]
