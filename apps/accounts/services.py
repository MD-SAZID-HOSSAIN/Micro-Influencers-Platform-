from django.db import IntegrityError

from apps.core.exceptions import Conflict, DomainError

from .models import Role, User


class RoleNotAllowed(DomainError):
    status_code = 400
    default_code = "role_not_allowed"
    default_detail = "This role cannot be chosen at registration."


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
