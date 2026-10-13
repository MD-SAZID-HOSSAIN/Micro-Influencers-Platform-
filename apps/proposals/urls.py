from django.urls import path

from .views import SubmitProposalView, WithdrawProposalView

urlpatterns = [
    path("campaigns/<int:pk>/proposals/", SubmitProposalView.as_view(), name="proposal-submit"),
    path(
        "creators/me/proposals/<int:pk>/withdraw/",
        WithdrawProposalView.as_view(),
        name="proposal-withdraw",
    ),
]
