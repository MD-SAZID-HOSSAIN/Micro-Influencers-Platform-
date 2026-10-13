from django.urls import path

from .views import ManualStatsView, MyStatsListView

urlpatterns = [
    path("creators/me/stats/", MyStatsListView.as_view(), name="creator-stats"),
    path("creators/me/stats/<str:platform>/", ManualStatsView.as_view(), name="creator-stats-manual"),
]
