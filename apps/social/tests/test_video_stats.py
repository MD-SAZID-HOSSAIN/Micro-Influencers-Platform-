from urllib.parse import parse_qs, urlparse

import pytest
import responses

from apps.social.youtube_client import (
    QuotaExceeded,
    TransientApiError,
    VideoStats,
    YouTubeClient,
    YouTubeError,
    youtube_video_id,
)

VIDEOS = "https://www.googleapis.com/youtube/v3/videos"


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?si=abc", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=too-short", None),
        ("https://www.youtube.com/@somechannel", None),
        ("https://www.youtube.com/playlist?list=PL123", None),
        ("https://www.instagram.com/p/dQw4w9WgXcQ/", None),
        ("https://evil.example.com/watch?v=dQw4w9WgXcQ", None),
        ("https://notyoutube.com/watch?v=dQw4w9WgXcQ", None),
        ("javascript:alert(1)", None),
        ("", None),
    ],
)
def test_video_id_is_extracted_from_the_common_youtube_url_shapes(url, expected):
    assert youtube_video_id(url) == expected


@responses.activate
def test_fetch_video_stats_sends_one_request_with_the_server_key_and_no_user_token():
    responses.get(
        VIDEOS,
        json={
            "items": [
                {"id": "aaaaaaaaaaa", "statistics": {"viewCount": "1500", "likeCount": "90", "commentCount": "12"}},
                {"id": "bbbbbbbbbbb", "statistics": {"viewCount": "700"}},  # likes and comments hidden
            ]
        },
    )

    stats = YouTubeClient().fetch_video_stats(["aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc"], "my-api-key")

    assert stats == {
        "aaaaaaaaaaa": VideoStats(views=1500, likes=90, comments=12),
        "bbbbbbbbbbb": VideoStats(views=700, likes=None, comments=None),
    }  # a video Google does not return (deleted, private) is simply absent
    assert len(responses.calls) == 1
    request = responses.calls[0].request
    query = parse_qs(urlparse(request.url).query)
    assert query["id"] == ["aaaaaaaaaaa,bbbbbbbbbbb,ccccccccccc"]
    assert query["key"] == ["my-api-key"]
    assert query["part"] == ["statistics"]
    assert "Authorization" not in request.headers


@responses.activate
def test_fetch_video_stats_with_no_ids_makes_no_request():
    assert YouTubeClient().fetch_video_stats([], "key") == {}
    assert len(responses.calls) == 0


@responses.activate
def test_quota_exhaustion_is_a_transient_error():
    body = '{"error": {"code": 403, "errors": [{"reason": "quotaExceeded"}]}}'
    responses.get(VIDEOS, status=403, body=body, content_type="application/json")

    with pytest.raises(QuotaExceeded):
        YouTubeClient().fetch_video_stats(["aaaaaaaaaaa"], "key")


@responses.activate
def test_server_errors_are_transient_and_a_bad_key_is_a_plain_error():
    responses.get(VIDEOS, status=503, json={})
    with pytest.raises(TransientApiError):
        YouTubeClient().fetch_video_stats(["aaaaaaaaaaa"], "key")

    responses.replace(
        responses.GET,
        VIDEOS,
        status=400,
        body='{"error": {"code": 400, "errors": [{"reason": "keyInvalid"}]}}',
        content_type="application/json",
    )
    with pytest.raises(YouTubeError) as caught:
        YouTubeClient().fetch_video_stats(["aaaaaaaaaaa"], "bad-key")
    assert not isinstance(caught.value, TransientApiError)


# ---- the API key must never reach an error message or a log ---------------------------------------
# `requests` puts the full URL (query string included) into its network error text, and the server's
# API key travels in that query string.

SECRET_KEY_VALUE = "AIzaSy-THE-SECRET-SERVER-KEY"


@responses.activate
def test_a_network_failure_does_not_carry_the_request_url_or_the_key():
    import traceback

    import requests

    url = f"{VIDEOS}?part=statistics&id=aaaaaaaaaaa&key={SECRET_KEY_VALUE}"
    responses.get(
        VIDEOS, body=requests.exceptions.ConnectionError(f"Max retries exceeded with url: {url}")
    )

    with pytest.raises(TransientApiError) as caught:
        YouTubeClient().fetch_video_stats(["aaaaaaaaaaa"], SECRET_KEY_VALUE)

    assert SECRET_KEY_VALUE not in str(caught.value)
    assert SECRET_KEY_VALUE not in "".join(traceback.format_exception(caught.value))  # nor the chained cause


@responses.activate
@pytest.mark.parametrize("failure", ["connection", "timeout"])
def test_the_daily_sync_never_logs_the_key_when_google_is_unreachable(db, settings, monkeypatch, caplog, failure):
    import logging

    import requests

    from apps.accounts.models import Role
    from apps.accounts.tests.factories import UserFactory
    from apps.campaigns.models import Campaign
    from apps.campaigns.tests.factories import CampaignFactory
    from apps.proposals.deliverable_stats import refresh_deliverable_stats
    from apps.proposals.models import Deliverable, Proposal
    from apps.proposals.tests.factories import ProposalFactory

    settings.YOUTUBE_API_KEY = SECRET_KEY_VALUE
    monkeypatch.setattr("apps.social.services.get_youtube_client", lambda: YouTubeClient())
    proposal = ProposalFactory(
        campaign=CampaignFactory(status=Campaign.Status.PUBLISHED), status=Proposal.Status.ACCEPTED
    )
    Deliverable.objects.create(
        proposal=proposal, post_url="https://youtu.be/aaaaaaaaaaa", platform="youtube"
    )
    error_class = {"connection": requests.exceptions.ConnectionError, "timeout": requests.exceptions.ConnectTimeout}
    responses.get(
        VIDEOS,
        body=error_class[failure](f"HTTPSConnectionPool: Max retries exceeded with url: /youtube/v3/videos?key={SECRET_KEY_VALUE}"),
    )

    with caplog.at_level(logging.DEBUG):
        refresh_deliverable_stats()

    assert "Could not fetch statistics" in caplog.text  # the failure IS reported...
    assert SECRET_KEY_VALUE not in caplog.text  # ...without the secret
    assert Role.CREATOR and UserFactory  # (imports kept for factory side effects)


def test_the_http_library_cannot_log_request_urls_even_if_debug_logging_is_switched_on():
    """urllib3 logs every request path, query string included, at DEBUG level."""
    import logging

    # An explicit level on the library's own logger, so turning on DEBUG for the root logger cannot undo it.
    assert logging.getLogger("urllib3").level == logging.WARNING
