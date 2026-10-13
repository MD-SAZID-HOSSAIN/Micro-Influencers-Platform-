"""One-time 6-digit codes (password reset now, email verification later).

Rules: a code expires after 10 minutes, works once, and is locked after 5 wrong
attempts. Only an HMAC of the code is stored.
"""
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import DomainError

from .models import OneTimeCode, User

CODE_TTL = timedelta(minutes=10)
MAX_ATTEMPTS = 5


class CodeInvalid(DomainError):
    status_code = 400
    default_code = "invalid_reset_code"
    default_detail = "The code is incorrect."


class CodeExpired(DomainError):
    status_code = 400
    default_code = "reset_code_expired"
    default_detail = "This code has expired. Request a new one."


class CodeUsed(DomainError):
    status_code = 400
    default_code = "reset_code_used"
    default_detail = "This code has already been used."


class CodeLocked(DomainError):
    status_code = 400
    default_code = "reset_code_locked"
    default_detail = "Too many incorrect attempts. Request a new code."


class VerificationCodeInvalid(CodeInvalid):
    default_code = "invalid_verification_code"


class VerificationCodeExpired(CodeExpired):
    default_code = "verification_code_expired"


class VerificationCodeUsed(CodeUsed):
    default_code = "verification_code_used"


class VerificationCodeLocked(CodeLocked):
    default_code = "verification_code_locked"


# Error classes per purpose, so each flow reports codes that make sense to its own screen.
_ERRORS = {
    "password_reset": {
        "invalid": CodeInvalid,
        "used": CodeUsed,
        "locked": CodeLocked,
        "expired": CodeExpired,
    },
    "email_verification": {
        "invalid": VerificationCodeInvalid,
        "used": VerificationCodeUsed,
        "locked": VerificationCodeLocked,
        "expired": VerificationCodeExpired,
    },
}


def _hash(user_id: int, purpose: str, code: str) -> str:
    message = f"{purpose}:{user_id}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def issue_code(user: User, purpose: str) -> str:
    """Create a fresh code (voiding earlier unused ones) and return it in plaintext once."""
    code = f"{secrets.randbelow(10**6):06d}"
    now = timezone.now()
    with transaction.atomic():
        OneTimeCode.objects.filter(user=user, purpose=purpose, used_at__isnull=True).update(
            used_at=now
        )
        OneTimeCode.objects.create(
            user=user,
            purpose=purpose,
            code_hash=_hash(user.pk, purpose, code),
            expires_at=now + CODE_TTL,
        )
    return code


def verify_code(user: User, purpose: str, code: str) -> None:
    """Consume ``code`` if it is the user's current valid code, else raise a code error.

    The outcome is decided inside a row-locked transaction so attempts and single-use
    hold under concurrency; the exception is raised afterwards so the attempt counter
    is committed rather than rolled back.
    """
    errors = _ERRORS[purpose]
    failure: type[DomainError] | None = None
    with transaction.atomic():
        current = (
            OneTimeCode.objects.select_for_update()
            .filter(user=user, purpose=purpose)
            .order_by("-created_at", "-id")
            .first()
        )
        if current is None:
            failure = errors["invalid"]
        elif current.used_at is not None:
            failure = errors["used"]
        elif current.attempts >= MAX_ATTEMPTS:
            failure = errors["locked"]
        elif timezone.now() > current.expires_at:
            failure = errors["expired"]
        elif hmac.compare_digest(current.code_hash, _hash(user.pk, purpose, code)):
            current.used_at = timezone.now()
            current.save(update_fields=["used_at"])
        else:
            current.attempts += 1
            current.save(update_fields=["attempts"])
            failure = errors["invalid"]
    if failure is not None:
        raise failure()
