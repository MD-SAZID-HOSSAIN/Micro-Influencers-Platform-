import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.social.models import PlatformStats


@pytest.fixture
def creator(db):
    return UserFactory(role=Role.CREATOR)


def test_social_challenge_generates_code(creator, auth_client):
    client = auth_client(creator)
    res = client.get("/api/v1/social/challenge/instagram/")
    assert res.status_code == 200
    data = res.json()
    assert data["platform"] == "instagram"
    assert data["challenge_code"].startswith("MIC-")
    assert "instructions" in data


def test_direct_connect_with_challenge_success(creator, auth_client):
    client = auth_client(creator)
    # 1. Get challenge
    ch = client.get("/api/v1/social/challenge/instagram/").json()
    code = ch["challenge_code"]

    # 2. Submit challenge code
    res = client.post(
        "/api/v1/social/direct-connect/instagram/",
        {
            "handle": "@rajon_creative",
            "verification_method": "challenge",
            "auth_code": code,
            "followers": 35000,
            "engagement_rate": "4.20",
        },
        format="json",
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_verified"] is True
    assert data["handle_url"] == "https://instagram.com/rajon_creative"
    assert data["followers"] == 35000


def test_direct_connect_with_challenge_wrong_code_fails(creator, auth_client):
    client = auth_client(creator)
    client.get("/api/v1/social/challenge/instagram/")

    res = client.post(
        "/api/v1/social/direct-connect/instagram/",
        {
            "handle": "@someone_else",
            "verification_method": "challenge",
            "auth_code": "WRONG-CODE",
            "followers": 1000000,
        },
        format="json",
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "challenge_failed"


def test_direct_connect_with_direct_auth(creator, auth_client):
    client = auth_client(creator)
    res = client.post(
        "/api/v1/social/direct-connect/facebook/",
        {
            "handle": "RajonOfficialPage",
            "verification_method": "direct_auth",
            "followers": 18500,
            "engagement_rate": "3.50",
        },
        format="json",
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_verified"] is True
    assert data["handle_url"] == "https://facebook.com/RajonOfficialPage"
    assert data["followers"] == 18500
