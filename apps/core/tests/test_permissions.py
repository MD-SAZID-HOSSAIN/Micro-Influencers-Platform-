from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser

from apps.core.permissions import IsAdminRole, IsBrand, IsCreator


def _request(role=None, authenticated=True):
    if not authenticated:
        return SimpleNamespace(user=AnonymousUser())
    return SimpleNamespace(user=SimpleNamespace(is_authenticated=True, role=role))


@pytest.mark.parametrize(
    "permission, allowed_role",
    [(IsCreator, "creator"), (IsBrand, "brand"), (IsAdminRole, "admin")],
)
def test_permission_allows_only_its_role(permission, allowed_role):
    for role in ("creator", "brand", "admin"):
        granted = permission().has_permission(_request(role), view=None)
        assert granted is (role == allowed_role)


@pytest.mark.parametrize("permission", [IsCreator, IsBrand, IsAdminRole])
def test_permission_denies_unauthenticated(permission):
    assert permission().has_permission(_request(authenticated=False), view=None) is False
