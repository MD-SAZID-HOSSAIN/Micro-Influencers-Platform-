from django.urls import path

from .brand_views import (
    BrandSocialAccountView,
    BrandSocialListView,
    BrandYouTubeCompleteView,
    BrandYouTubeConnectView,
)
from .views import (
    DirectAccountConnectView,
    FacebookConnectView,
    InstagramConnectView,
    ManualStatsView,
    MyStatsListView,
    SocialChallengeView,
    YouTubeCallbackView,
    YouTubeCompleteView,
    YouTubeConnectionView,
    YouTubeConnectView,
    YouTubeDirectConnectView,
    YouTubeRecentContentView,
    YouTubeRefreshView,
)

urlpatterns = [
    path("social/youtube/", YouTubeConnectionView.as_view(), name="youtube-connection"),
    path("social/youtube/connect/", YouTubeConnectView.as_view(), name="youtube-connect"),
    path("social/youtube/direct-connect/", YouTubeDirectConnectView.as_view(), name="youtube-direct-connect"),
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
    path("social/challenge/<str:platform>/", SocialChallengeView.as_view(), name="social-challenge"),
    path("social/direct-connect/<str:platform>/", DirectAccountConnectView.as_view(), name="social-direct-connect"),
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

