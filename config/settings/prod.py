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
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
