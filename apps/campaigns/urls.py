from django.urls import path

from .views import (
    BrandCampaignDetailView,
    CampaignAnalyticsView,
    BrandCampaignListCreateView,
    CloseCampaignView,
    CreatorCampaignDetailView,
    CreatorCampaignListView,
    PublishCampaignView,
)

urlpatterns = [
    path(
        "brand/campaigns/<int:pk>/analytics/",
        CampaignAnalyticsView.as_view(),
        name="brand-campaign-analytics",
    ),
    path("campaigns/", CreatorCampaignListView.as_view(), name="campaigns"),
    path("campaigns/<int:pk>/", CreatorCampaignDetailView.as_view(), name="campaign-detail"),
    path("brand/campaigns/", BrandCampaignListCreateView.as_view(), name="brand-campaigns"),
    path("brand/campaigns/<int:pk>/", BrandCampaignDetailView.as_view(), name="brand-campaign"),
    path(
        "brand/campaigns/<int:pk>/publish/",
        PublishCampaignView.as_view(),
        name="brand-campaign-publish",
    ),
    path(
        "brand/campaigns/<int:pk>/close/", CloseCampaignView.as_view(), name="brand-campaign-close"
    ),
]
