from rest_framework.permissions import BasePermission

# Literal values of accounts.Role; kept as strings so core does not import accounts.
CREATOR = "creator"
BRAND = "brand"
ADMIN = "admin"


class _HasRole(BasePermission):
    role = ""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and getattr(user, "role", None) == self.role
        )


class IsCreator(_HasRole):
    role = CREATOR


class IsBrand(_HasRole):
    role = BRAND


class IsAdminRole(_HasRole):
    role = ADMIN
