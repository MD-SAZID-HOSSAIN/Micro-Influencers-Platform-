from django.urls import path

from .views import (
    AcceptProposalView,
    BrandProposalListView,
    CampaignContentPerformanceView,
    CampaignDeliverablesView,
    CompleteProposalView,
    DeliverableDetailView,
    DeliverableListCreateView,
    MyProposalListView,
    RejectProposalView,
    ShortlistProposalView,
    SubmitProposalView,
    WithdrawProposalView,
)

urlpatterns = [
    path(
        "brand/campaigns/<int:pk>/analytics/content/",
        CampaignContentPerformanceView.as_view(),
        name="campaign-content-performance",
    ),
    path(
        "creators/me/proposals/<int:pk>/deliverables/",
        DeliverableListCreateView.as_view(),
        name="deliverables",
    ),
    path(
        "creators/me/proposals/<int:pk>/deliverables/<int:deliverable_id>/",
        DeliverableDetailView.as_view(),
        name="deliverable",
    ),
    path("brand/proposals/<int:pk>/complete/", CompleteProposalView.as_view(), name="proposal-complete"),
    path(
        "brand/campaigns/<int:pk>/deliverables/",
        CampaignDeliverablesView.as_view(),
        name="campaign-deliverables",
    ),
    path("creators/me/proposals/", MyProposalListView.as_view(), name="my-proposals"),
    path("brand/proposals/<int:pk>/shortlist/", ShortlistProposalView.as_view(), name="proposal-shortlist"),
    path("brand/proposals/<int:pk>/accept/", AcceptProposalView.as_view(), name="proposal-accept"),
    path("brand/proposals/<int:pk>/reject/", RejectProposalView.as_view(), name="proposal-reject"),
    path(
        "brand/campaigns/<int:pk>/proposals/",
        BrandProposalListView.as_view(),
        name="brand-campaign-proposals",
    ),
    path("campaigns/<int:pk>/proposals/", SubmitProposalView.as_view(), name="proposal-submit"),
    path(
        "creators/me/proposals/<int:pk>/withdraw/",
        WithdrawProposalView.as_view(),
        name="proposal-withdraw",
    ),
]
