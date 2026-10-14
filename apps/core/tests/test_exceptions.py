import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.urls("apps.core.tests.urls_errors")


def test_domain_error_uses_envelope():
    response = APIClient().get("/conflict/")

    assert response.status_code == 409
    assert response.json() == {
        "error": {"code": "conflict", "message": "Already exists.", "details": None}
    }


def test_validation_error_has_details_per_field():
    response = APIClient().post("/validate/", {}, format="json")

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"] == "Invalid input."
    assert error["details"]["name"] == ["This field is required."]


def test_404_uses_envelope():
    response = APIClient().get("/missing/")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["details"] is None


def test_unauthenticated_uses_envelope_and_keeps_401():
    response = APIClient().get("/needs-auth/")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
