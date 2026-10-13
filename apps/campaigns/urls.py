from django.urls import path

from .views import (
    BrandCampaignDetailView,
    BrandCampaignListCreateView,
    CloseCampaignView,
    PublishCampaignView,
)

urlpatterns = [
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
