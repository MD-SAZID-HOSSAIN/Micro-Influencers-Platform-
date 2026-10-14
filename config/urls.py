from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.profiles.urls")),
    path("api/v1/", include("apps.social.urls")),
    path("api/v1/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.campaigns.urls")),
    path("api/v1/", include("apps.proposals.urls")),
    path("api/v1/", include("apps.dashboards.urls")),
    path("api/v1/", include("apps.reviews.urls")),
    path("api/v1/", include("apps.adminpanel.urls")),
]

# JSON versions of Django's HTML 404/500 pages, so every error uses the same envelope.
handler404 = "apps.core.views.not_found"
handler500 = "apps.core.views.server_error"
