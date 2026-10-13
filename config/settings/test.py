from .base import *  # noqa: F401,F403

SECRET_KEY = "test-secret-key-not-for-production"
DEBUG = False

# Fast hasher for tests only; production keeps Django's default PBKDF2 hasher.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False

# Test-only credentials; real ones come from the environment.
OAUTH_ENCRYPTION_KEY = "0123456789abcdef0123456789abcdef0123456789a="
GOOGLE_CLIENT_ID = "test-client-id"
GOOGLE_CLIENT_SECRET = "test-client-secret"
GOOGLE_REDIRECT_URI = "http://testserver/api/v1/social/youtube/callback/"
FRONTEND_URL = "http://frontend.test"
CORS_ALLOWED_ORIGINS = ["http://frontend.test"]

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
