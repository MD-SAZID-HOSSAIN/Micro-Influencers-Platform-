from .base import *  # noqa: F401,F403
from .base import env

DEBUG = True
SECRET_KEY = env("SECRET_KEY", default="dev-insecure-key-change-me")
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
