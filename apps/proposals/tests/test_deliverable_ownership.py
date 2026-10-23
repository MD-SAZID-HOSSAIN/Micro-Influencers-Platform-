"""A YouTube deliverable must be a video on the creator's own channel.

Otherwise a creator could submit somebody else's popular video and have its views and likes shown to the brand as
their own results. The check needs the server's YouTube key; when Google cannot answer, the link is accepted and
the daily statistics sync makes the same comparison before it stores any number.
"""
import pytest

from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.proposals.models import Deliverable, Proposal
from apps.proposals.tests.factories import ProposalFactory
from apps.social.tests.fakes import FakeYouTubeClient, make_connection
from apps.social.youtube_client import TransientApiError, VideoStats

OWN = "UC-mine"
VIDEO = "abcdefghijk"  # 11 characters
URL = f"https://www.youtube.com/watch?v={VIDEO}"


@pytest.fixture
def fake(monkeypatch):
    client = FakeYouTubeClient()
    monkeypatch.setattr("apps.social.services.get_youtube_client", lambda: client)
    return client


@pytest.fixture
def accepted(db):
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED, creators_needed=3)
    proposal = ProposalFactory(campaign=campaign, status=Proposal.Status.ACCEPTED)
    make_connection(proposal.creator, channel_id=OWN, with_stats=False)
    return proposal


def add(auth_client, proposal, url=URL, platform="youtube"):
    return auth_client(proposal.creator).post(
        f"/api/v1/creators/me/proposals/{proposal.pk}/deliverables/",
        {"post_url": url, "platform": platform, "note": ""},
        format="json",
    )


def error_code(response):
    return response.json()["error"]["code"]


def test_a_video_on_the_creators_own_channel_is_accepted(accepted, fake, auth_client):
    fake.video_results[VIDEO] = VideoStats(10, 1, 1, channel_id=OWN)

    assert add(auth_client, accepted).status_code == 201


def test_a_video_from_another_channel_is_refused(accepted, fake, auth_client):
    fake.video_results[VIDEO] = VideoStats(9_000_000, 500_000, 20_000, channel_id="UC-a-famous-channel")

    response = add(auth_client, accepted)

    assert response.status_code == 400 and error_code(response) == "video_not_yours"
    assert not Deliverable.objects.filter(proposal=accepted).exists()


def test_changing_a_link_to_someone_elses_video_is_refused(accepted, fake, auth_client):
    fake.video_results[VIDEO] = VideoStats(10, 1, 1, channel_id=OWN)
    created = add(auth_client, accepted).json()
    other = "zyxwvutsrqp"
    fake.video_results[other] = VideoStats(9_000_000, 1, 1, channel_id="UC-a-famous-channel")

    response = auth_client(accepted.creator).patch(
        f"/api/v1/creators/me/proposals/{accepted.pk}/deliverables/{created['id']}/",
        {"post_url": f"https://youtu.be/{other}"},
        format="json",
    )

    assert response.status_code == 400 and error_code(response) == "video_not_yours"
    assert Deliverable.objects.get(pk=created["id"]).post_url == URL


def test_editing_only_the_note_does_not_call_google(accepted, fake, auth_client):
    fake.video_results[VIDEO] = VideoStats(10, 1, 1, channel_id=OWN)
    created = add(auth_client, accepted).json()
    calls_before = len(fake.video_calls)

    response = auth_client(accepted.creator).patch(
        f"/api/v1/creators/me/proposals/{accepted.pk}/deliverables/{created['id']}/",
        {"note": "Posted on Monday"},
        format="json",
    )

    assert response.status_code == 200 and len(fake.video_calls) == calls_before


def test_a_video_google_does_not_return_is_accepted(accepted, fake, auth_client):
    assert add(auth_client, accepted).status_code == 201  # private or deleted: nothing to compare


def test_when_google_is_unavailable_the_link_is_accepted_for_the_daily_check(accepted, fake, auth_client):
    fake.video_batch_errors = [TransientApiError("503")]

    assert add(auth_client, accepted).status_code == 201


def test_without_the_server_key_nothing_is_checked(accepted, fake, auth_client, settings):
    settings.YOUTUBE_API_KEY = ""
    fake.video_results[VIDEO] = VideoStats(10, 1, 1, channel_id="UC-a-famous-channel")

    assert add(auth_client, accepted).status_code == 201
    assert fake.video_calls == []


def test_a_creator_whose_channel_is_not_known_yet_is_not_blocked(fake, auth_client, db):
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED, creators_needed=3)
    proposal = ProposalFactory(campaign=campaign, status=Proposal.Status.ACCEPTED)
    fake.video_results[VIDEO] = VideoStats(10, 1, 1, channel_id="UC-anyone")

    assert add(auth_client, proposal).status_code == 201


def test_other_platforms_are_not_checked(accepted, fake, auth_client):
    response = add(auth_client, accepted, url="https://www.instagram.com/p/abc/", platform="instagram")

    assert response.status_code == 201 and fake.video_calls == []
