from django.urls import path

from .views import CreateReviewView, CreatorReviewsView

urlpatterns = [
    path("brand/proposals/<int:pk>/review/", CreateReviewView.as_view(), name="proposal-review"),
    path("creators/<int:user_id>/reviews/", CreatorReviewsView.as_view(), name="creator-reviews"),
]
