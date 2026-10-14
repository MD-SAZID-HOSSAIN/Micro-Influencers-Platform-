from django.urls import path

from .views import BrandDashboardView, CreatorDashboardView

urlpatterns = [
    path("creators/me/dashboard/", CreatorDashboardView.as_view(), name="creator-dashboard"),
    path("brands/me/dashboard/", BrandDashboardView.as_view(), name="brand-dashboard"),
]
