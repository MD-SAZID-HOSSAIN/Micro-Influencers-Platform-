from django.urls import path

from .views import CreatorDashboardView

urlpatterns = [
    path("creators/me/dashboard/", CreatorDashboardView.as_view(), name="creator-dashboard"),
]
