from .base import *  # noqa: F401,F403

SECRET_KEY = "test-secret-key-not-for-production"
DEBUG = False

# Fast hasher for tests only; production keeps Django's default PBKDF2 hasher.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
