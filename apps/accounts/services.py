from django.contrib.auth.hashers import make_password
from django.db import IntegrityError
from django.db.models import F
from rest_framework_simplejwt.tokens import AccessToken

from apps.core.exceptions import Conflict, DomainError

from .models import Role, User


class RoleNotAllowed(DomainError):
    status_code = 400
    default_code = "role_not_allowed"
    default_detail = "This role cannot be chosen at registration."


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
        return User.objects.create_user(
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
