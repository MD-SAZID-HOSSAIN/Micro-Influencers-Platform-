import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.urls("apps.core.tests.urls_errors")


def test_default_page_size_is_20():
    body = APIClient().get("/numbers/").json()

    assert body["count"] == 120
    assert len(body["results"]) == 20


def test_page_size_param_is_honoured():
    body = APIClient().get("/numbers/?page_size=5").json()

    assert len(body["results"]) == 5


def test_pagination_caps_page_size_at_50():
    body = APIClient().get("/numbers/?page_size=100").json()

    assert len(body["results"]) == 50
