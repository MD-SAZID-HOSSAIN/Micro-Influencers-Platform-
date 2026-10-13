from django.urls import path

from .views import (
    AcceptProposalView,
    BrandProposalListView,
    MyProposalListView,
    RejectProposalView,
    ShortlistProposalView,
    SubmitProposalView,
    WithdrawProposalView,
)

urlpatterns = [
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
