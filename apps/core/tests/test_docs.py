import pytest
from django.core.management import call_command
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_swagger_ui_is_served_publicly():
    response = APIClient().get("/api/docs/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_schema_is_served_publicly_and_lists_health():
    response = APIClient().get("/api/schema/?format=json")

    assert response.status_code == 200
    assert "/api/v1/health/" in response.json()["paths"]


def test_schema_generation_validates(tmp_path):
    call_command("spectacular", "--validate", "--fail-on-warn", "--file", str(tmp_path / "s.yml"))
