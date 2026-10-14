from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import (
    ALLOWED_HOSTS,
    CORS_ALLOWED_ORIGINS,
    OAUTH_ENCRYPTION_KEY,
    REST_FRAMEWORK,
    SECRET_KEY,
    env,
)

DEBUG = False

# Fail fast: a production process that starts with an unsafe configuration is worse than one that doesn't.
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY must be set in the environment for production.")
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must list the real host names (no wildcard).")
if not CORS_ALLOWED_ORIGINS or any(
    origin == "*" or not origin.startswith("https://") for origin in CORS_ALLOWED_ORIGINS
):
    raise ImproperlyConfigured("CORS_ALLOWED_ORIGINS must list the frontend's https:// origins (no wildcard).")
if not OAUTH_ENCRYPTION_KEY:
    raise ImproperlyConfigured("OAUTH_ENCRYPTION_KEY must be set so OAuth tokens can be encrypted at rest.")

# One reverse proxy (load balancer / nginx) terminates TLS in front of the app.
NUM_PROXIES = env.int("NUM_PROXIES", default=1)
REST_FRAMEWORK = {**REST_FRAMEWORK, "NUM_PROXIES": NUM_PROXIES}

# HTTPS everywhere. The proxy must set X-Forwarded-Proto and strip any client-supplied value.
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]  # so a plain-HTTP health probe is not redirected
# HSTS makes browsers use HTTPS only for this host. The two extra switches are hard to undo, so they are
# opt-in per deployment: `includeSubDomains` also locks every subdomain to HTTPS, and `preload` is a promise
# that can end up in browsers' built-in lists. Lower SECURE_HSTS_SECONDS (e.g. 300) for a first rollout.
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
if SECURE_HSTS_PRELOAD and not SECURE_HSTS_INCLUDE_SUBDOMAINS:
    raise ImproperlyConfigured(
        "SECURE_HSTS_PRELOAD requires SECURE_HSTS_INCLUDE_SUBDOMAINS=true: browsers reject a preload header without it."
    )

# Django's deployment check nags us to switch the two options above on. Leaving them off is a deliberate
# choice (see the comment above), so say so instead of turning irreversible options on to quiet a warning.
SILENCED_SYSTEM_CHECKS = []
if not SECURE_HSTS_INCLUDE_SUBDOMAINS:
    SILENCED_SYSTEM_CHECKS.append("security.W005")
if not SECURE_HSTS_PRELOAD:
    SILENCED_SYSTEM_CHECKS.append("security.W021")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
