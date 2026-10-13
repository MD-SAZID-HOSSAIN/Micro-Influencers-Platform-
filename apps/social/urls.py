from django.urls import path

from .views import ManualStatsView, MyStatsListView, YouTubeRefreshView

urlpatterns = [
    path("social/youtube/refresh/", YouTubeRefreshView.as_view(), name="youtube-refresh"),
    path("creators/me/stats/", MyStatsListView.as_view(), name="creator-stats"),
    path("creators/me/stats/<str:platform>/", ManualStatsView.as_view(), name="creator-stats-manual"),
]
