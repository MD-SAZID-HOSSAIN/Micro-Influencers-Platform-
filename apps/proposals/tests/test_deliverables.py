import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.proposals.models import Deliverable, Proposal
from apps.proposals.tests.factories import ProposalFactory

S = Proposal.Status


def list_url(pk):
    return f"/api/v1/creators/me/proposals/{pk}/deliverables/"


def item_url(pk, did):
    return f"/api/v1/creators/me/proposals/{pk}/deliverables/{did}/"


def complete_url(pk):
    return f"/api/v1/brand/proposals/{pk}/complete/"


def brand_list_url(campaign_id):
    return f"/api/v1/brand/campaigns/{campaign_id}/deliverables/"


def withdraw_url(pk):
    return f"/api/v1/creators/me/proposals/{pk}/withdraw/"


def body(**overrides):
    data = {"post_url": "https://www.instagram.com/p/abc123/", "platform": "instagram", "note": "Posted today"}
    data.update(overrides)
    return data


@pytest.fixture
def accepted(db):
    """An accepted proposal on a published campaign, and its creator."""
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED, creators_needed=3)
    return ProposalFactory(campaign=campaign, status=S.ACCEPTED)


def error_code(response):
    return response.json()["error"]["code"]


def add(auth_client, proposal, **overrides):
    return auth_client(proposal.creator).post(list_url(proposal.pk), body(**overrides), format="json")


# ---- submitting ------------------------------------------------------------------------------------


def test_creator_submits_links_to_the_published_content(accepted, auth_client):
    response = add(auth_client, accepted)

    assert response.status_code == 201
    data = response.json()
    assert data["post_url"] == "https://www.instagram.com/p/abc123/"
    assert data["platform"] == "instagram"
    assert data["note"] == "Posted today"
    assert Deliverable.objects.get(pk=data["id"]).proposal == accepted


def test_the_note_is_optional(accepted, auth_client):
    response = auth_client(accepted.creator).post(
        list_url(accepted.pk), {"post_url": "https://youtu.be/xyz", "platform": "youtube"}, format="json"
    )

    assert response.status_code == 201
    assert response.json()["note"] == ""


@pytest.mark.parametrize("status", [S.PENDING, S.SHORTLISTED, S.REJECTED, S.WITHDRAWN])
def test_only_accepted_proposals_can_have_deliverables(db, auth_client, status):
    proposal = ProposalFactory(status=status)

    response = add(auth_client, proposal)

    assert response.status_code == 409
    assert error_code(response) == "deliverables_locked"
    assert not Deliverable.objects.exists()


def test_deliverables_are_capped_per_proposal(accepted, auth_client):
    for n in range(20):
        assert add(auth_client, accepted, post_url=f"https://example.com/{n}").status_code == 201

    response = add(auth_client, accepted, post_url="https://example.com/one-too-many")

    assert response.status_code == 409
    assert error_code(response) == "deliverables_full"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,x", "//evil.com", "instagram.com/p/1"])
def test_unsafe_post_urls_are_rejected(accepted, auth_client, url):  # RF2
    response = add(auth_client, accepted, post_url=url)

    assert response.status_code == 400
    assert "post_url" in response.json()["error"]["details"]


def test_html_in_the_note_is_stripped(accepted, auth_client):  # RF2
    assert add(auth_client, accepted, note="<script>x</script>Done").json()["note"] == "xDone"


def test_platform_must_be_valid_and_url_is_required(accepted, auth_client):
    assert add(auth_client, accepted, platform="myspace").status_code == 400
    response = auth_client(accepted.creator).post(list_url(accepted.pk), {"platform": "youtube"}, format="json")
    assert response.status_code == 400
    assert "post_url" in response.json()["error"]["details"]


# ---- updating until completion ---------------------------------------------------------------------------


def test_creator_can_list_update_and_delete_until_completion(accepted, auth_client):
    created = add(auth_client, accepted).json()
    client = auth_client(accepted.creator)

    assert [d["id"] for d in client.get(list_url(accepted.pk)).json()] == [created["id"]]
    patched = client.patch(item_url(accepted.pk, created["id"]), {"note": "Updated"}, format="json")
    assert patched.status_code == 200 and patched.json()["note"] == "Updated"
    assert client.delete(item_url(accepted.pk, created["id"])).status_code == 204
    assert client.get(list_url(accepted.pk)).json() == []


def test_deliverables_are_locked_once_the_collaboration_is_completed(accepted, auth_client):
    created = add(auth_client, accepted).json()
    Proposal.objects.filter(pk=accepted.pk).update(completed_at=timezone.now())
    client = auth_client(accepted.creator)

    add_after = add(auth_client, accepted, post_url="https://example.com/late")
    patch_after = client.patch(item_url(accepted.pk, created["id"]), {"note": "late edit"}, format="json")
    delete_after = client.delete(item_url(accepted.pk, created["id"]))

    for response in (add_after, patch_after, delete_after):
        assert response.status_code == 409
        assert error_code(response) == "deliverables_locked"
    assert Deliverable.objects.get(pk=created["id"]).note == "Posted today"


def test_listing_works_after_completion_and_for_non_accepted_proposals(accepted, auth_client):
    add(auth_client, accepted)
    Proposal.objects.filter(pk=accepted.pk).update(completed_at=timezone.now())
    other = ProposalFactory(creator=accepted.creator, status=S.PENDING)

    assert len(auth_client(accepted.creator).get(list_url(accepted.pk)).json()) == 1
    assert auth_client(accepted.creator).get(list_url(other.pk)).json() == []


def test_creators_cannot_touch_each_others_deliverables(accepted, auth_client):  # RF3
    created = add(auth_client, accepted).json()
    intruder = UserFactory(role=Role.CREATOR)
    client = auth_client(intruder)

    assert client.get(list_url(accepted.pk)).status_code == 404
    assert client.post(list_url(accepted.pk), body(), format="json").status_code == 404
    assert client.patch(item_url(accepted.pk, created["id"]), {"note": "x"}, format="json").status_code == 404
    assert client.delete(item_url(accepted.pk, created["id"])).status_code == 404
    assert Deliverable.objects.get(pk=created["id"]).note == "Posted today"


def test_a_deliverable_id_from_another_proposal_is_not_found(accepted, auth_client):
    mine = ProposalFactory(creator=accepted.creator, status=S.ACCEPTED)
    created = add(auth_client, accepted).json()

    assert auth_client(accepted.creator).patch(
        item_url(mine.pk, created["id"]), {"note": "x"}, format="json"
    ).status_code == 404


# ---- the brand's side -------------------------------------------------------------------------------------------


def test_brand_views_each_accepted_creators_deliverables_from_the_campaign_page(accepted, auth_client):
    campaign = accepted.campaign
    add(auth_client, accepted, post_url="https://example.com/a")
    second = ProposalFactory(campaign=campaign, status=S.ACCEPTED)
    add(auth_client, second, post_url="https://example.com/b")
    ProposalFactory(campaign=campaign, status=S.PENDING)  # not accepted: not listed
    withdrawn = ProposalFactory(campaign=campaign, status=S.WITHDRAWN)
    Deliverable.objects.create(proposal=withdrawn, post_url="https://example.com/gone", platform="instagram")

    rows = auth_client(campaign.brand).get(brand_list_url(campaign.pk)).json()

    assert {r["proposal_id"] for r in rows} == {accepted.id, second.id}
    first_row = next(r for r in rows if r["proposal_id"] == accepted.id)
    assert first_row["creator"] == {"id": accepted.creator_id, "name": accepted.creator.full_name}
    assert first_row["completed_at"] is None
    assert [d["post_url"] for d in first_row["deliverables"]] == ["https://example.com/a"]


def test_an_accepted_creator_with_nothing_submitted_still_appears(accepted, auth_client):
    rows = auth_client(accepted.campaign.brand).get(brand_list_url(accepted.campaign_id)).json()

    assert rows[0]["proposal_id"] == accepted.id
    assert rows[0]["deliverables"] == []


def test_another_brands_campaign_deliverables_are_404(accepted, auth_client):  # RF3
    stranger = UserFactory(role=Role.BRAND)

    assert auth_client(stranger).get(brand_list_url(accepted.campaign_id)).status_code == 404


# ---- completion -------------------------------------------------------------------------------------------------


def test_brand_marks_an_accepted_proposal_completed(accepted, auth_client):
    response = auth_client(accepted.campaign.brand).post(complete_url(accepted.pk))

    assert response.status_code == 200
    body_ = response.json()
    assert body_["id"] == accepted.id and body_["status"] == "accepted"
    assert body_["completed_at"] is not None
    assert Proposal.objects.get(pk=accepted.pk).completed_at is not None


@pytest.mark.parametrize("status", [S.PENDING, S.SHORTLISTED, S.REJECTED, S.WITHDRAWN])
def test_only_accepted_proposals_can_be_completed(db, auth_client, status):
    proposal = ProposalFactory(status=status)

    response = auth_client(proposal.campaign.brand).post(complete_url(proposal.pk))

    assert response.status_code == 409
    assert error_code(response) == "invalid_transition"
    assert Proposal.objects.get(pk=proposal.pk).completed_at is None


def test_completion_is_final_and_repeating_it_changes_nothing(accepted, auth_client):
    client = auth_client(accepted.campaign.brand)
    first = client.post(complete_url(accepted.pk)).json()["completed_at"]

    second = client.post(complete_url(accepted.pk))

    assert second.status_code == 200
    assert second.json()["completed_at"] == first


def test_completion_is_tracked_per_creator(accepted, auth_client):
    other = ProposalFactory(campaign=accepted.campaign, status=S.ACCEPTED)

    auth_client(accepted.campaign.brand).post(complete_url(accepted.pk))

    assert Proposal.objects.get(pk=accepted.pk).completed_at is not None
    assert Proposal.objects.get(pk=other.pk).completed_at is None
    rows = auth_client(accepted.campaign.brand).get(brand_list_url(accepted.campaign_id)).json()
    assert {r["proposal_id"]: r["completed_at"] is not None for r in rows} == {accepted.id: True, other.id: False}


def test_a_completed_collaboration_cannot_be_withdrawn(accepted, auth_client):
    auth_client(accepted.campaign.brand).post(complete_url(accepted.pk))

    response = auth_client(accepted.creator).post(withdraw_url(accepted.pk), {"reason": "Changed my mind"}, format="json")

    assert response.status_code == 409
    assert error_code(response) == "already_completed"
    assert Proposal.objects.get(pk=accepted.pk).status == S.ACCEPTED


def test_a_completed_collaboration_cannot_be_rejected_or_shortlisted(accepted, auth_client):
    client = auth_client(accepted.campaign.brand)
    client.post(complete_url(accepted.pk))

    assert client.post(f"/api/v1/brand/proposals/{accepted.pk}/reject/").status_code == 409
    assert client.post(f"/api/v1/brand/proposals/{accepted.pk}/shortlist/").status_code == 409


def test_completion_does_not_free_the_slot(accepted, auth_client):
    auth_client(accepted.campaign.brand).post(complete_url(accepted.pk))

    campaign_view = auth_client(accepted.creator).get(f"/api/v1/campaigns/{accepted.campaign_id}/").json()

    assert campaign_view["accepted_count"] == 1


def test_completed_at_appears_in_the_proposal_lists(accepted, auth_client):
    auth_client(accepted.campaign.brand).post(complete_url(accepted.pk))

    mine = auth_client(accepted.creator).get("/api/v1/creators/me/proposals/").json()["results"][0]
    theirs = auth_client(accepted.campaign.brand).get(
        f"/api/v1/brand/campaigns/{accepted.campaign_id}/proposals/"
    ).json()["results"][0]

    assert mine["completed_at"] is not None and theirs["completed_at"] is not None


def test_another_brands_proposal_cannot_be_completed(accepted, auth_client):  # RF3
    stranger = UserFactory(role=Role.BRAND)

    response = auth_client(stranger).post(complete_url(accepted.pk))

    assert response.status_code == 404
    assert Proposal.objects.get(pk=accepted.pk).completed_at is None


# ---- roles ---------------------------------------------------------------------------------------------------------


def test_roles_are_enforced(accepted, auth_client):
    brand, creator = accepted.campaign.brand, accepted.creator

    assert auth_client(brand).get(list_url(accepted.pk)).status_code == 403
    assert auth_client(creator).post(complete_url(accepted.pk)).status_code == 403
    assert auth_client(creator).get(brand_list_url(accepted.campaign_id)).status_code == 403
    assert APIClient().get(list_url(accepted.pk)).status_code == 401
    assert APIClient().post(complete_url(accepted.pk)).status_code == 401
