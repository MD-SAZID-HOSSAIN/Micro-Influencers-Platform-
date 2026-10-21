from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from apps.core.emailing import queue_email
from apps.core.exceptions import Conflict, DomainError

from .codes import CODE_TTL, CodeInvalid, issue_code, verify_code
from .models import CodePurpose, OneTimeCode, Role, User


class RoleNotAllowed(DomainError):
    status_code = 400
    default_code = "role_not_allowed"
    default_detail = "This role cannot be chosen at registration."


class AlreadyVerified(Conflict):
    default_code = "already_verified"
    default_detail = "Your email address is already verified."


class ResendCooldown(DomainError):
    status_code = 429
    default_code = "resend_cooldown"
    default_detail = "A code was sent a moment ago. Please wait a minute before asking for another."


RESEND_COOLDOWN = timedelta(seconds=60)


class InvalidCredentials(DomainError):
    status_code = 401
    default_code = "invalid_credentials"
    default_detail = "Invalid email/username or password."


def register_user(
    *,
    role: str,
    full_name: str,
    email: str,
    username: str,
    password: str,
    mobile_number: str,
) -> User:
    if role not in (Role.CREATOR, Role.BRAND):
        raise RoleNotAllowed()
    try:
        user = User.objects.create_user(
            username=username,
            email=email.strip().lower(),
            password=password,
            full_name=full_name,
            mobile_number=mobile_number,
            role=role,
        )
    except IntegrityError:
        # Lost a race against a concurrent registration of the same email/username.
        raise Conflict("Email or username is already in use.")
    request_email_verification(user)  # brands and creators both confirm their address with a 6-digit code
    return user


def authenticate_login(identifier: str, password: str) -> User:
    """Return the active user matching email-or-username and password, else raise."""
    identifier = (identifier or "").strip()
    user = (
        User.objects.filter(email__iexact=identifier).first()
        or User.objects.filter(username__iexact=identifier).first()
    )
    if user is None:
        make_password(password)  # keep timing similar whether or not the user exists
        raise InvalidCredentials()
    if not user.check_password(password) or not user.is_active:
        raise InvalidCredentials()
    return user


def issue_access_token(user: User) -> str:
    token = AccessToken.for_user(user)
    token["tv"] = user.token_version
    return str(token)


def bump_token_version(user: User) -> None:
    """Invalidate every token issued so far for this user."""
    User.objects.filter(pk=user.pk).update(token_version=F("token_version") + 1)


GENERIC_RESET_MESSAGE = "If this email is registered, a code has been sent."


def _find_active_user_by_email(email: str) -> User | None:
    return User.objects.filter(email__iexact=(email or "").strip(), is_active=True).first()


def request_password_reset(email: str) -> None:
    """Email a reset code if the address belongs to an active user; otherwise do nothing."""
    user = _find_active_user_by_email(email)
    if user is None:
        return
    code = issue_code(user, CodePurpose.PASSWORD_RESET)
    transaction.on_commit(
        lambda: queue_email(
            user.email,
            "Your password reset code",
            "password_reset",
            {"code": code, "expires_minutes": int(CODE_TTL.total_seconds() // 60)},
        )
    )


def request_email_verification(user: User) -> str:
    """Email a fresh 6-digit verification code. Always sent, whatever the notification toggle says."""
    code = issue_code(user, CodePurpose.EMAIL_VERIFICATION)
    transaction.on_commit(
        lambda: queue_email(
            user.email,
            "Verify your email address",
            "verify_email",
            {"code": code, "expires_minutes": int(CODE_TTL.total_seconds() // 60)},
        )
    )
    return code


def resend_email_verification(user: User) -> str:
    """Send a new verification code, at most one per minute."""
    if user.email_verified:
        raise AlreadyVerified()
    latest = (
        OneTimeCode.objects.filter(user=user, purpose=CodePurpose.EMAIL_VERIFICATION)
        .order_by("-created_at")
        .first()
    )
    if latest is not None and timezone.now() - latest.created_at < RESEND_COOLDOWN:
        raise ResendCooldown()
    return request_email_verification(user)


def verify_email(user: User, code: str) -> User:
    """Mark the address verified if ``code`` is the user's current valid verification code."""
    verify_code(user, CodePurpose.EMAIL_VERIFICATION, code)
    User.objects.filter(pk=user.pk).update(email_verified=True)
    user.email_verified = True
    return user


def confirm_password_reset(email: str, code: str, new_password: str) -> None:
    """Set a new password if ``code`` is valid, and sign the user out everywhere."""
    user = _find_active_user_by_email(email)
    if user is None:
        raise CodeInvalid()
    verify_code(user, CodePurpose.PASSWORD_RESET, code)
    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=["password"])
        bump_token_version(user)
