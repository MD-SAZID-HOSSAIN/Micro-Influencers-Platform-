from django.urls import path

from .views import BrandDetailView, BrandMeView, CreatorMeView

urlpatterns = [
    path("creators/me/", CreatorMeView.as_view(), name="creator-me"),
    path("brands/me/", BrandMeView.as_view(), name="brand-me"),
    path("brands/<int:user_id>/", BrandDetailView.as_view(), name="brand-detail"),
]
