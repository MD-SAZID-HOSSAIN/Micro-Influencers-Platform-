from django.urls import path

from .views import (
    BrandDetailView,
    BrandMeView,
    CreatorMeView,
    PortfolioDeleteView,
    PortfolioListCreateView,
)

urlpatterns = [
    path("creators/me/", CreatorMeView.as_view(), name="creator-me"),
    path("creators/me/portfolio/", PortfolioListCreateView.as_view(), name="portfolio"),
    path("creators/me/portfolio/<int:pk>/", PortfolioDeleteView.as_view(), name="portfolio-item"),
    path("brands/me/", BrandMeView.as_view(), name="brand-me"),
    path("brands/<int:user_id>/", BrandDetailView.as_view(), name="brand-detail"),
]
