from django.urls import path

from .views import BrandProposalListView, SubmitProposalView, WithdrawProposalView

urlpatterns = [
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
