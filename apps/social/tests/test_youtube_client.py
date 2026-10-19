import json
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest
import requests
import responses

from apps.social.youtube_client import (
    ChannelNotFound,
    QuotaExceeded,
    SubscribersHidden,
    TokenRevoked,
    TransientApiError,
    YouTubeClient,
)

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"


@pytest.fixture
def client():
    return YouTubeClient()


# ---- authorization URL ---------------------------------------------------------------


def test_auth_url_has_readonly_scope_and_state(client):
    url = client.build_auth_url("signed-state")

    parsed = urlparse(url)
    query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://accounts.google.com/o/oauth2/v2/auth"
    assert query["state"] == "signed-state"
    assert query["scope"] == "https://www.googleapis.com/auth/youtube.readonly"
    assert query["client_id"] == "test-client-id"
    assert query["redirect_uri"] == "http://testserver/api/v1/social/youtube/callback/"
    assert query["response_type"] == "code"
    assert query["access_type"] == "offline"
    assert query["prompt"] == "consent"


# ---- token endpoint --------------------------------------------------------------------


@responses.activate
def test_exchange_code_returns_tokens_and_sends_expected_form(client):
    responses.post(
        TOKEN_URL,
        json={"access_token": "at", "refresh_token": "rt", "expires_in": 3599, "token_type": "Bearer"},
    )

    tokens = client.exchange_code("the-code")

    assert (tokens.access_token, tokens.refresh_token, tokens.expires_in) == ("at", "rt", 3599)
    form = parse_qs(responses.calls[0].request.body)
    assert form["code"] == ["the-code"]
    assert form["grant_type"] == ["authorization_code"]
    assert form["client_id"] == ["test-client-id"]
    assert form["client_secret"] == ["test-client-secret"]
    assert form["redirect_uri"] == ["http://testserver/api/v1/social/youtube/callback/"]


@responses.activate
def test_refresh_access_token_without_new_refresh_token(client):
    responses.post(TOKEN_URL, json={"access_token": "new-at", "expires_in": 3599})

    tokens = client.refresh_access_token("rt")

    assert tokens.access_token == "new-at"
    assert tokens.refresh_token is None
    assert parse_qs(responses.calls[0].request.body)["grant_type"] == ["refresh_token"]


@responses.activate
@pytest.mark.parametrize("call", ["exchange", "refresh"])
def test_invalid_grant_raises_token_revoked(client, call):
    responses.post(TOKEN_URL, status=400, json={"error": "invalid_grant"})

    with pytest.raises(TokenRevoked):
        if call == "exchange":
            client.exchange_code("x")
        else:
            client.refresh_access_token("x")


# ---- channel snapshot ------------------------------------------------------------------


def mock_channel(*, custom_url="@amina", subscribers="12345", hidden=False, uploads="UU123", channel_id="UC1"):
    item = {
        "id": channel_id,
        "snippet": {"customUrl": custom_url} if custom_url else {},
        "statistics": {"subscriberCount": subscribers, "hiddenSubscriberCount": hidden},
        "contentDetails": {"relatedPlaylists": {"uploads": uploads}} if uploads else {},
    }
    responses.get(f"{API}/channels", json={"items": [item]})


def mock_videos(videos):
    """videos: list of dicts with id, views, likes, comments (likes/comments may be None)."""
    responses.get(
        f"{API}/playlistItems",
        json={"items": [{"contentDetails": {"videoId": v["id"]}} for v in videos]},
    )
    items = []
    for v in videos:
        stats = {"viewCount": str(v["views"])}
        if v.get("likes") is not None:
            stats["likeCount"] = str(v["likes"])
        if v.get("comments") is not None:
            stats["commentCount"] = str(v["comments"])
        items.append(
            {
                "id": v["id"],
                "snippet": {"title": f"Video {v['id']}", "publishedAt": "2026-10-01T10:00:00Z"},
                "statistics": stats,
            }
        )
    responses.get(f"{API}/videos", json={"items": items})


@responses.activate
def test_fetch_channel_computes_engagement_rate(client):
    mock_channel()
    videos = [
        {"id": f"v{i}", "views": 1000 + i * 100, "likes": 30 + i, "comments": 5 + i} for i in range(10)
    ]
    mock_videos(videos)

    snapshot = client.fetch_channel("access-token")

    total_views = sum(v["views"] for v in videos)
    interactions = sum(v["likes"] + v["comments"] for v in videos)
    expected = (Decimal(interactions) / Decimal(total_views) * 100).quantize(Decimal("0.01"))
    assert snapshot.engagement_rate == expected
    assert snapshot.subscribers == 12345
    assert snapshot.handle_url == "https://www.youtube.com/@amina"
    assert len(snapshot.recent_content) == 10
    assert snapshot.recent_content[0] == {
        "video_id": "v0",
        "title": "Video v0",
        "url": "https://www.youtube.com/watch?v=v0",
        "published_at": "2026-10-01T10:00:00Z",
    }


@responses.activate
def test_engagement_rate_exact_value(client):
    mock_channel()
    mock_videos([{"id": "a", "views": 10000, "likes": 300, "comments": 75}])

    assert client.fetch_channel("t").engagement_rate == Decimal("3.75")


@responses.activate
def test_requests_the_last_10_uploads_with_a_bearer_token(client):
    mock_channel()
    mock_videos([{"id": "a", "views": 1, "likes": 0, "comments": 0}])

    client.fetch_channel("my-access-token")

    assert all(c.request.headers["Authorization"] == "Bearer my-access-token" for c in responses.calls)
    playlist_call = next(c for c in responses.calls if "/playlistItems" in c.request.url)
    query = parse_qs(urlparse(playlist_call.request.url).query)
    assert query["maxResults"] == ["10"]
    assert query["playlistId"] == ["UU123"]


@responses.activate
def test_hidden_like_and_comment_counts_count_as_zero(client):
    mock_channel()
    mock_videos([{"id": "a", "views": 1000, "likes": None, "comments": None}])

    assert client.fetch_channel("t").engagement_rate == Decimal("0.00")


@responses.activate
def test_zero_views_gives_zero_engagement(client):
    mock_channel()
    mock_videos([{"id": "a", "views": 0, "likes": 5, "comments": 5}])

    assert client.fetch_channel("t").engagement_rate == Decimal("0.00")


@responses.activate
def test_channel_without_uploads_has_zero_engagement_and_no_content(client):
    mock_channel(uploads=None)

    snapshot = client.fetch_channel("t")

    assert snapshot.engagement_rate == Decimal("0.00")
    assert snapshot.recent_content == []
    assert len(responses.calls) == 1  # no playlist or video calls were needed


@responses.activate
def test_handle_falls_back_to_channel_url(client):
    mock_channel(custom_url=None, channel_id="UCabc")
    mock_videos([{"id": "a", "views": 1, "likes": 0, "comments": 0}])

    assert client.fetch_channel("t").handle_url == "https://www.youtube.com/channel/UCabc"


@responses.activate
def test_hidden_subscriber_count_is_reported_not_stored_as_zero(client):
    mock_channel(subscribers="0", hidden=True)

    with pytest.raises(SubscribersHidden):
        client.fetch_channel("t")


@responses.activate
def test_google_account_without_a_channel_raises_channel_not_found(client):
    responses.get(f"{API}/channels", json={"items": []})

    with pytest.raises(ChannelNotFound):
        client.fetch_channel("t")


# ---- error mapping ---------------------------------------------------------------------


@responses.activate
def test_401_raises_token_revoked(client):
    responses.get(f"{API}/channels", status=401, json={"error": {"code": 401}})

    with pytest.raises(TokenRevoked):
        client.fetch_channel("t")


@responses.activate
@pytest.mark.parametrize("status", [500, 502, 503, 429])
def test_server_errors_and_rate_limits_are_transient(client, status):
    responses.get(f"{API}/channels", status=status, json={})

    with pytest.raises(TransientApiError):
        client.fetch_channel("t")


@responses.activate
def test_quota_error_raises_quota_exceeded_which_is_transient(client):
    body = {"error": {"code": 403, "errors": [{"reason": "quotaExceeded"}]}}
    responses.get(f"{API}/channels", status=403, body=json.dumps(body), content_type="application/json")

    with pytest.raises(QuotaExceeded) as caught:
        client.fetch_channel("t")

    assert isinstance(caught.value, TransientApiError)


@responses.activate
def test_withdrawn_permission_raises_token_revoked(client):
    body = {"error": {"code": 403, "errors": [{"reason": "insufficientPermissions"}]}}
    responses.get(f"{API}/channels", status=403, body=json.dumps(body), content_type="application/json")

    with pytest.raises(TokenRevoked):
        client.fetch_channel("t")


@responses.activate
@pytest.mark.parametrize("exc", [requests.exceptions.ConnectTimeout(), requests.exceptions.ConnectionError()])
def test_network_failures_are_transient(client, exc):
    responses.get(f"{API}/channels", body=exc)

    with pytest.raises(TransientApiError):
        client.fetch_channel("t")


# ---- revoking, error text, and the engagement cap ---------------------------------------------------------------


@responses.activate
def test_revoke_token_posts_the_token_to_googles_revoke_endpoint(client):
    responses.post("https://oauth2.googleapis.com/revoke", status=200, json={})

    client.revoke_token("the-refresh-token")

    assert parse_qs(responses.calls[0].request.body) == {"token": ["the-refresh-token"]}


@responses.activate
def test_revoking_a_token_google_already_dropped_is_fine(client):
    responses.post("https://oauth2.googleapis.com/revoke", status=400, json={"error": "invalid_token"})

    client.revoke_token("old")  # no error


@responses.activate
def test_a_failed_revoke_is_an_error(client):
    responses.post("https://oauth2.googleapis.com/revoke", status=503)

    with pytest.raises(TransientApiError):
        client.revoke_token("t")


@responses.activate
def test_error_messages_carry_googles_reason_but_not_the_request(client):
    responses.post(TOKEN_URL, status=400, json={"error": "invalid_grant"})

    with pytest.raises(TokenRevoked) as raised:
        client.exchange_code("the-code")

    assert "invalid_grant" in str(raised.value)
    assert "the-code" not in str(raised.value) and "test-client-secret" not in str(raised.value)


@responses.activate
def test_engagement_rate_is_capped_to_fit_its_database_column(client):
    mock_channel()
    mock_videos([{"id": "a", "views": 1, "likes": 50, "comments": 20}])  # 7000% before the cap

    assert client.fetch_channel("t").engagement_rate == Decimal("999.99")
