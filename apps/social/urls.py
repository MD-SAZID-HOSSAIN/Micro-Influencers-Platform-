from django.urls import path

from .views import (
    ManualStatsView,
    MyStatsListView,
    YouTubeCallbackView,
    YouTubeCompleteView,
    YouTubeConnectionView,
    YouTubeConnectView,
    YouTubeRecentContentView,
    YouTubeRefreshView,
)

urlpatterns = [
    path("social/youtube/", YouTubeConnectionView.as_view(), name="youtube-connection"),
    path("social/youtube/connect/", YouTubeConnectView.as_view(), name="youtube-connect"),
    path("social/youtube/callback/", YouTubeCallbackView.as_view(), name="youtube-callback"),
    path("social/youtube/complete/", YouTubeCompleteView.as_view(), name="youtube-complete"),
    path("social/youtube/refresh/", YouTubeRefreshView.as_view(), name="youtube-refresh"),
    path(
        "social/youtube/recent-content/",
        YouTubeRecentContentView.as_view(),
        name="youtube-recent-content",
    ),
    path("creators/me/stats/", MyStatsListView.as_view(), name="creator-stats"),
    path(
        "creators/me/stats/<str:platform>/",
        ManualStatsView.as_view(),
        name="creator-stats-manual",
    ),
]
