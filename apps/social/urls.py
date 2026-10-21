from django.urls import path

from .brand_views import (
    BrandSocialAccountView,
    BrandSocialListView,
    BrandYouTubeCompleteView,
    BrandYouTubeConnectView,
)
from .views import (
    FacebookConnectView,
    InstagramConnectView,
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
    path("social/instagram/connect/", InstagramConnectView.as_view(), name="instagram-connect"),
    path("social/facebook/connect/", FacebookConnectView.as_view(), name="facebook-connect"),
    path("brands/me/social/", BrandSocialListView.as_view(), name="brand-social"),
    path("brands/me/social/youtube/connect/", BrandYouTubeConnectView.as_view(), name="brand-youtube-connect"),
    path("brands/me/social/youtube/complete/", BrandYouTubeCompleteView.as_view(), name="brand-youtube-complete"),
    path("brands/me/social/<str:platform>/", BrandSocialAccountView.as_view(), name="brand-social-account"),
    path("creators/me/stats/", MyStatsListView.as_view(), name="creator-stats"),
    path(
        "creators/me/stats/<str:platform>/",
        ManualStatsView.as_view(),
        name="creator-stats-manual",
    ),
]

