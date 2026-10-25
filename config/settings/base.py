from datetime import timedelta
from pathlib import Path

import environ
from celery.schedules import crontab

from config.bootstrap import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv()  # same .env handling as manage.py / wsgi / celery (see config/bootstrap.py)
env = environ.Env()

SECRET_KEY = env("SECRET_KEY", default="")
DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "apps.core",
    "apps.accounts",
    "apps.profiles",
    "apps.social",
    "apps.notifications",
    "apps.campaigns",
    "apps.proposals",
    "apps.dashboards",
    "apps.reviews",
    "apps.adminpanel",
]

AUTH_USER_MODEL = "accounts.User"

# Upload size limits (photos for campaigns and profile pictures; videos for campaigns).
MEDIA_MAX_PHOTO_BYTES = 5 * 1024 * 1024
MEDIA_MAX_VIDEO_BYTES = 50 * 1024 * 1024
# false = refuse every file upload. For a host whose disk is wiped on each deploy (no persistent storage), so an
# upload is never accepted and then lost. Profile pictures and logos can still be set from a pasted link.
UPLOADS_ENABLED = env.bool("UPLOADS_ENABLED", default=True)

# Applied when someone registers or resets a password (not when an admin is created on the server).
# The 8-character minimum is enforced by the serializers' own `min_length`.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Inert for bearer-token API views (DRF exempts them from CSRF); kept so the standard
    # deployment checks pass without silencing anything.
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        # Needed for Swagger UI and plain-text email templates.
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://postgres:postgres@localhost:5432/microinfluencers",
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        # Without timeouts a Redis outage makes every throttled request wait for the OS to give up.
        "OPTIONS": {"socket_connect_timeout": 2, "socket_timeout": 2},
    }
}

# How many reverse proxies sit in front of the app. Throttling identifies clients by IP, and
# with this unset DRF would trust the whole X-Forwarded-For header, which any client can fake.
# 0 = no proxy, use the connecting address; production defaults to 1 (see prod.py).
NUM_PROXIES = env.int("NUM_PROXIES", default=0)

REST_FRAMEWORK = {
    # Deny by default: a new view is protected unless it explicitly opts out.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.VersionedJWTAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "NUM_PROXIES": NUM_PROXIES,
    "DEFAULT_THROTTLE_RATES": {
        "register": "5/min",
        "login": "10/min",
        "password_reset": "5/hour",
        "password_reset_confirm": "10/hour",
        "email_verify": "20/hour",
        "email_resend": "5/hour",
        "admin_login": "5/min",
        "youtube_complete": "20/hour",
    },
}

# How long an admin stays logged in. 0 (the default) means the login does not expire in practice (10 years): the admin
# stays logged in until they press Log out or their password changes. A number of minutes sets a limit instead.
ADMIN_TOKEN_MINUTES = env.int("ADMIN_TOKEN_MINUTES", default=0)

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=24),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Micro-Influencers' Platform API",
    "DESCRIPTION": (
        "REST API for the two-sided creator / brand marketplace.\n\n"
        "## Authentication\n"
        "Log in with `POST /auth/login/` and send the returned token on every other request as "
        "`Authorization: Bearer <token>`. Tokens last 24 hours. Only the endpoints without a "
        "padlock in this document are public.\n\n"
        "## Errors\n"
        "Every error has the same shape: "
        '`{"error": {"code": "...", "message": "...", "details": ...}}`. `code` is stable and '
        "meant for the frontend to branch on; `details` holds per-field messages for validation "
        "errors (HTTP 400) and is `null` otherwise.\n\n"
        "## Pagination\n"
        "List endpoints return `count`, `next`, `previous` and `results`. Use `page` and "
        "`page_size` (default 20, maximum 50)."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "TAGS": [
        {"name": "Health", "description": "Liveness probe used by deployments."},
        {"name": "Auth", "description": "Registration, login, logout and password reset."},
        {"name": "Profiles", "description": "Creator and brand profiles, and the creator's portfolio."},
        {"name": "Social", "description": "Platform stats, YouTube connection (OAuth) and manual stats entry."},
        {"name": "Discovery", "description": "Brand-facing creator directory and creator-facing campaign directory."},
        {"name": "Campaigns", "description": "A brand's campaigns: create, edit, publish and close."},
        {"name": "Proposals", "description": "Applying to campaigns and managing the proposals received."},
        {"name": "Reviews", "description": "Ratings and reviews of creators after completed collaborations."},
        {"name": "Notifications", "description": "In-app notifications."},
        {"name": "Dashboards", "description": "The creator and brand home screens."},
        {"name": "Admin", "description": "The admin panel: user management, moderation and platform overview."},
    ],
    "ENUM_NAME_OVERRIDES": {
        "PlatformEnum": "apps.core.choices.Platform",
        "NicheEnum": "apps.core.choices.Niche",
        "CampaignStatusEnum": "apps.campaigns.models.Campaign.Status",
        "YouTubeConnectionStatusEnum": "apps.social.models.YouTubeConnection.Status",
        "ProposalStatusEnum": "apps.proposals.models.Proposal.Status",
        "RoleEnum": "apps.accounts.models.Role",
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "loggers": {
        # urllib3 logs every outgoing request path, query string included, at DEBUG. One of our calls
        # carries the YouTube API key in its query string, so keep this library quiet whatever the root level.
        "urllib3": {"level": "WARNING"},
    },
}

FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

MEDIA_URL = env("MEDIA_URL", default="/media/")
MEDIA_ROOT = Path(env("MEDIA_ROOT", default="") or BASE_DIR / "media")  # blank means the default; needs persistent storage when deployed

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TIMEZONE = "UTC"
# true = run background jobs (emails, the first YouTube sync) inside the request instead of queueing them. For a
# deployment with no Celery worker, such as a free Render plan. The scheduled daily jobs still need a beat process.
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = False
# A failed email is retried later by the worker. With no worker (jobs run inside the request) a retry would only hold the
# request open, so the failure is logged with its reason instead. Read from the environment value, not the dev default.
EMAIL_RETRY_ON_FAILURE = not CELERY_TASK_ALWAYS_EAGER
CELERY_BEAT_SCHEDULE = {
    "sync-all-youtube": {
        "task": "apps.social.tasks.sync_all_youtube",
        "schedule": crontab(hour=3, minute=0),
    },
    "sync-deliverable-stats": {
        "task": "apps.proposals.tasks.sync_deliverable_stats",
        "schedule": crontab(hour=4, minute=0),
    },
    "close-expired-campaigns": {
        "task": "apps.campaigns.tasks.close_expired_campaigns",
        "schedule": crontab(minute="*/5"),
    },
}

YOUTUBE_REFRESH_COOLDOWN_SECONDS = 900
# A creator is Verified, and may apply, only with at least this many YouTube subscribers.
MIN_CREATOR_FOLLOWERS = env.int("MIN_CREATOR_FOLLOWERS", default=1000)
# The daily YouTube sync starts creators evenly over this many seconds (0 = all at once).
YOUTUBE_SYNC_SPREAD_SECONDS = 1800

EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
# Seconds to wait for the mail server. Without a limit a wrong host or login can hold a request open for minutes.
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")

OAUTH_ENCRYPTION_KEY = env("OAUTH_ENCRYPTION_KEY", default="")
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", default="")
GOOGLE_REDIRECT_URI = env("GOOGLE_REDIRECT_URI", default="")
# Server-side key for public YouTube video statistics (content performance); optional.
YOUTUBE_API_KEY = env("YOUTUBE_API_KEY", default="")
