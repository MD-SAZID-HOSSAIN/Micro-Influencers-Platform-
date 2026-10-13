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
