import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_ok_without_auth():
    response = APIClient().get("/api/v1/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.urls("apps.core.tests.urls_throwaway")
def test_unlisted_route_requires_auth():
    response = APIClient().get("/unlisted/")

    assert response.status_code == 401
