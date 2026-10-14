"""Encryption of OAuth tokens at rest (Fernet: AES-128-CBC + HMAC)."""
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _fernet() -> Fernet:
    key = settings.OAUTH_ENCRYPTION_KEY
    if not key:
        raise ImproperlyConfigured("OAUTH_ENCRYPTION_KEY is not set.")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured("OAUTH_ENCRYPTION_KEY is not a valid Fernet key.") from exc


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    """Raises ``cryptography.fernet.InvalidToken`` for a wrong key or tampered data."""
    return _fernet().decrypt(token.encode()).decode()
