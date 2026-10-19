from django.urls import path

from .views import (
    BrandCampaignDetailView,
    CampaignAnalyticsView,
    CampaignMediaCreateView,
    CampaignMediaDeleteView,
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
    path(
        "brand/campaigns/<int:pk>/media/",
        CampaignMediaCreateView.as_view(),
        name="brand-campaign-media",
    ),
    path(
        "brand/campaigns/<int:pk>/media/<int:media_id>/",
        CampaignMediaDeleteView.as_view(),
        name="brand-campaign-media-item",
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
