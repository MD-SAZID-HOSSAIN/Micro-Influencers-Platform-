from django.urls import path

from .directory_views import CreatorDetailView, CreatorDirectoryView
from .views import (
    BrandDetailView,
    BrandLogoUploadView,
    BrandMeView,
    CreatorMeView,
    CreatorPhotoUploadView,
    PortfolioDeleteView,
    PortfolioListCreateView,
)

urlpatterns = [
    path("creators/me/", CreatorMeView.as_view(), name="creator-me"),
    path("creators/me/photo/", CreatorPhotoUploadView.as_view(), name="creator-photo-upload"),
    path("creators/me/portfolio/", PortfolioListCreateView.as_view(), name="portfolio"),
    path("creators/me/portfolio/<int:pk>/", PortfolioDeleteView.as_view(), name="portfolio-item"),
    path("creators/", CreatorDirectoryView.as_view(), name="creator-directory"),
    path("creators/<int:user_id>/", CreatorDetailView.as_view(), name="creator-detail"),
    path("brands/me/", BrandMeView.as_view(), name="brand-me"),
    path("brands/me/logo/", BrandLogoUploadView.as_view(), name="brand-logo-upload"),
    path("brands/<int:user_id>/", BrandDetailView.as_view(), name="brand-detail"),
]
