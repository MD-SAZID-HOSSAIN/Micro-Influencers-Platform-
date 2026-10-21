from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory
from apps.adminpanel.models import AdminActionLog
from apps.campaigns.models import Campaign
from apps.campaigns.tests.factories import CampaignFactory
from apps.notifications.models import Kind
from apps.notifications.services import notify
from apps.profiles.models import CreatorProfile
from apps.proposals.models import Proposal
from apps.proposals.tests.factories import ProposalFactory
from apps.reviews.models import Review
from apps.reviews.services import recalculate_rating

ADMIN_LOGIN = "/api/v1/admin/auth/login/"
PUBLIC_LOGIN = "/api/v1/auth/login/"
USERS = "/api/v1/admin/users/"
ACTIONS = "/api/v1/admin/actions/"
OVERVIEW = "/api/v1/admin/overview/"
REASON = "Reported for spam by several brands."


def user_url(pk, action=""):
    return f"/api/v1/admin/users/{pk}/{action}"


def campaign_close_url(pk):
    return f"/api/v1/admin/campaigns/{pk}/close/"


def review_url(pk):
    return f"/api/v1/admin/reviews/{pk}/"


@pytest.fixture
def admin(db):
    return UserFactory(role=Role.ADMIN, username="root_admin")


def error_code(response):
    return response.json()["error"]["code"]


def delete_with_reason(client, url, reason=REASON):
    return client.delete(url, {"reason": reason}, format="json")


# ---- a separate login for the panel ------------------------------------------------------------------------


def login(path, identifier, password=DEFAULT_PASSWORD):
    return APIClient().post(path, {"identifier": identifier, "password": password}, format="json")


def test_admins_log_in_through_the_admin_endpoint(admin):
    response = login(ADMIN_LOGIN, "root_admin")

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"
    assert response.json()["access"]


@pytest.mark.parametrize("role", [Role.CREATOR, Role.BRAND])
def test_ordinary_accounts_cannot_use_the_admin_login(db, role):
    UserFactory(role=role, username="someone")

    response = login(ADMIN_LOGIN, "someone")

    assert response.status_code == 401
    assert error_code(response) == "invalid_credentials"


def test_the_public_login_does_not_accept_admin_accounts(admin):
    response = login(PUBLIC_LOGIN, "root_admin")

    assert response.status_code == 401
    assert error_code(response) == "invalid_credentials"


def test_a_wrong_admin_password_gives_the_same_error_as_an_unknown_account(admin):
    wrong = login(ADMIN_LOGIN, "root_admin", "nope-nope-nope")
    unknown = login(ADMIN_LOGIN, "nobody", "nope-nope-nope")

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_an_admin_token_opens_the_panel_but_an_ordinary_token_does_not(admin, auth_client):
    creator = UserFactory(role=Role.CREATOR)

    assert auth_client(admin).get(USERS).status_code == 200
    assert auth_client(creator).get(USERS).status_code == 403
    assert APIClient().get(USERS).status_code == 401


# ---- listing users -------------------------------------------------------------------------------------------


def test_users_list_shows_status_and_supports_search_and_filters(admin, auth_client):
    amina = UserFactory(role=Role.CREATOR, full_name="Amina Rahman", username="aminar", email="amina@x.com")
    brand = UserFactory(role=Role.BRAND, full_name="Acme Owner", username="acme", is_active=False)
    client = auth_client(admin)

    def ids(**params):
        return {u["id"] for u in client.get(USERS, params).json()["results"]}

    assert ids(q="rahman") == {amina.id}
    assert ids(q="ACME") == {brand.id}
    assert ids(q="amina@x") == {amina.id}
    assert ids(role="brand") == {brand.id}
    assert ids(status="suspended") == {brand.id}
    assert amina.id in ids(status="active") and brand.id not in ids(status="active")
    row = next(u for u in client.get(USERS, {"q": "acme"}).json()["results"] if u["id"] == brand.id)
    assert row["status"] == "suspended" and row["role"] == "brand" and "date_joined" in row
    assert "password" not in row


def test_users_list_validates_filters_and_paginates(admin, auth_client):
    for _ in range(25):
        UserFactory()
    client = auth_client(admin)

    page = client.get(USERS).json()

    assert page["count"] == 26 and len(page["results"]) == 20
    assert client.get(USERS, {"role": "wizard"}).status_code == 400
    assert client.get(USERS, {"status": "banned"}).status_code == 400


# ---- suspending and reactivating ------------------------------------------------------------------------------


def test_suspending_blocks_login_and_existing_tokens_and_is_logged(admin, auth_client):
    target = UserFactory(role=Role.CREATOR, username="spammer")
    target_client = auth_client(target)
    assert target_client.get("/api/v1/auth/me/").status_code == 200

    response = auth_client(admin).post(user_url(target.pk, "suspend/"), {"reason": REASON}, format="json")

    assert response.status_code == 200
    assert response.json()["status"] == "suspended"
    target.refresh_from_db()
    assert target.is_active is False
    assert login(PUBLIC_LOGIN, "spammer").status_code == 401
    assert target_client.get("/api/v1/auth/me/").status_code == 401  # the token stops working at once
    entry = AdminActionLog.objects.get()
    assert (entry.admin, entry.action, entry.target_type, entry.target_id, entry.reason) == (
        admin,
        "user.suspend",
        "user",
        target.pk,
        REASON,
    )
    assert entry.target_label == "spammer"
    assert abs(entry.created_at - timezone.now()) < timedelta(seconds=5)


def test_reactivating_restores_login(admin, auth_client):
    target = UserFactory(role=Role.CREATOR, username="returning", is_active=False)

    response = auth_client(admin).post(user_url(target.pk, "reactivate/"), {"reason": "Appeal accepted."}, format="json")

    assert response.status_code == 200 and response.json()["status"] == "active"
    assert login(PUBLIC_LOGIN, "returning").status_code == 200
    assert AdminActionLog.objects.get().action == "user.reactivate"


def test_suspending_twice_or_reactivating_an_active_user_is_a_conflict(admin, auth_client):
    active = UserFactory()
    suspended = UserFactory(is_active=False)
    client = auth_client(admin)

    again = client.post(user_url(suspended.pk, "suspend/"), {"reason": REASON}, format="json")
    pointless = client.post(user_url(active.pk, "reactivate/"), {"reason": REASON}, format="json")

    assert (again.status_code, error_code(again)) == (409, "already_suspended")
    assert (pointless.status_code, error_code(pointless)) == (409, "already_active")
    assert not AdminActionLog.objects.exists()


def test_suspended_users_get_no_emails_but_keep_in_app_notifications(admin, auth_client, run_on_commit):
    target = UserFactory(role=Role.CREATOR, email_verified=True)
    auth_client(admin).post(user_url(target.pk, "suspend/"), {"reason": REASON}, format="json")
    target.refresh_from_db()

    with run_on_commit():
        notify(target, Kind.PROPOSAL_ACCEPTED, "Accepted")

    assert mail.outbox == []


@pytest.mark.parametrize("action", ["suspend/", "reactivate/"])
def test_unknown_users_are_404(admin, auth_client, action):
    assert auth_client(admin).post(user_url(999999, action), {"reason": REASON}, format="json").status_code == 404


# ---- admins cannot act on themselves -----------------------------------------------------------------------------


def test_an_admin_cannot_suspend_or_delete_themselves(admin, auth_client):
    client = auth_client(admin)

    suspend = client.post(user_url(admin.pk, "suspend/"), {"reason": REASON}, format="json")
    delete = delete_with_reason(client, user_url(admin.pk))

    for response in (suspend, delete):
        assert response.status_code == 409
        assert error_code(response) == "cannot_modify_self"
    admin.refresh_from_db()
    assert admin.is_active is True and User.objects.filter(pk=admin.pk).exists()
    assert not AdminActionLog.objects.exists()


# ---- every action needs a reason --------------------------------------------------------------------------------------


@pytest.mark.parametrize("reason", [None, "", "   ", "<b></b>", "x" * 501])
def test_every_action_requires_a_real_reason_and_changes_nothing_without_one(admin, auth_client, reason):
    victim = UserFactory(role=Role.CREATOR)
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED)
    proposal = ProposalFactory(status=Proposal.Status.ACCEPTED, completed_at=timezone.now())
    review = Review.objects.create(proposal=proposal, brand=proposal.campaign.brand, creator=proposal.creator, rating=1)
    client = auth_client(admin)
    body = {} if reason is None else {"reason": reason}

    responses = [
        client.post(user_url(victim.pk, "suspend/"), body, format="json"),
        client.post(campaign_close_url(campaign.pk), body, format="json"),
        client.delete(user_url(victim.pk), body, format="json"),
        client.delete(review_url(review.pk), body, format="json"),
    ]

    for response in responses:
        assert response.status_code == 400
        assert "reason" in response.json()["error"]["details"]
    assert not AdminActionLog.objects.exists()
    assert User.objects.get(pk=victim.pk).is_active
    assert Campaign.objects.get(pk=campaign.pk).status == Campaign.Status.PUBLISHED
    assert Review.objects.filter(pk=review.pk).exists()


def test_html_is_stripped_from_the_reason(admin, auth_client):
    target = UserFactory()

    auth_client(admin).post(user_url(target.pk, "suspend/"), {"reason": "<script>x</script>Spam"}, format="json")

    assert AdminActionLog.objects.get().reason == "xSpam"


# ---- deleting users ----------------------------------------------------------------------------------------------------


def test_deleting_a_user_removes_their_data_and_keeps_a_log_entry_that_names_them(admin, auth_client):
    target = UserFactory(role=Role.CREATOR, username="doomed")
    ProposalFactory(creator=target)

    response = delete_with_reason(auth_client(admin), user_url(target.pk))

    assert response.status_code == 204
    assert not User.objects.filter(pk=target.pk).exists()
    assert not Proposal.objects.filter(creator_id=target.pk).exists()
    entry = AdminActionLog.objects.get()
    assert (entry.action, entry.target_id, entry.target_label) == ("user.delete", target.pk, "doomed")


def test_deleting_a_brand_recalculates_the_ratings_it_gave(admin, auth_client):
    creator = UserFactory(role=Role.CREATOR)
    good = ProposalFactory(creator=creator, status=Proposal.Status.ACCEPTED, completed_at=timezone.now())
    bad = ProposalFactory(creator=creator, status=Proposal.Status.ACCEPTED, completed_at=timezone.now())
    Review.objects.create(proposal=good, brand=good.campaign.brand, creator=creator, rating=5)
    Review.objects.create(proposal=bad, brand=bad.campaign.brand, creator=creator, rating=1)
    recalculate_rating(creator.id)
    assert CreatorProfile.objects.get(user=creator).rating_count == 2

    delete_with_reason(auth_client(admin), user_url(bad.campaign.brand_id))

    profile = CreatorProfile.objects.get(user=creator)
    assert (profile.rating_count, str(profile.rating_avg)) == (1, "5.00")


def test_deleting_an_unknown_user_is_404(admin, auth_client):
    assert delete_with_reason(auth_client(admin), user_url(999999)).status_code == 404


def test_the_log_survives_the_deletion_of_the_admin_who_wrote_it(admin, auth_client):
    other_admin = UserFactory(role=Role.ADMIN, username="second_admin")
    target = UserFactory()
    auth_client(other_admin).post(user_url(target.pk, "suspend/"), {"reason": REASON}, format="json")

    delete_with_reason(auth_client(admin), user_url(other_admin.pk))

    suspend_entry = AdminActionLog.objects.get(action="user.suspend")
    assert suspend_entry.admin is None
    assert suspend_entry.admin_label == "second_admin"


# ---- moderation ----------------------------------------------------------------------------------------------------------


def test_an_admin_can_close_a_published_campaign(admin, auth_client):
    campaign = CampaignFactory(status=Campaign.Status.PUBLISHED)

    response = auth_client(admin).post(campaign_close_url(campaign.pk), {"reason": "Misleading offer."}, format="json")

    assert response.status_code == 200 and response.json()["status"] == "closed"
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.CLOSED
    entry = AdminActionLog.objects.get()
    assert (entry.action, entry.target_type, entry.target_id) == ("campaign.close", "campaign", campaign.pk)


def test_closing_a_draft_is_rejected_and_closing_a_closed_campaign_is_a_no_op(admin, auth_client):
    draft = CampaignFactory(status=Campaign.Status.DRAFT)
    closed = CampaignFactory(status=Campaign.Status.CLOSED)
    client = auth_client(admin)

    assert client.post(campaign_close_url(draft.pk), {"reason": REASON}, format="json").status_code == 409
    assert client.post(campaign_close_url(closed.pk), {"reason": REASON}, format="json").status_code == 200
    assert client.post(campaign_close_url(999999), {"reason": REASON}, format="json").status_code == 404


def test_removing_a_review_recalculates_the_rating_and_is_logged(admin, auth_client):
    creator = UserFactory(role=Role.CREATOR)
    keep = ProposalFactory(creator=creator, status=Proposal.Status.ACCEPTED, completed_at=timezone.now())
    abusive = ProposalFactory(creator=creator, status=Proposal.Status.ACCEPTED, completed_at=timezone.now())
    Review.objects.create(proposal=keep, brand=keep.campaign.brand, creator=creator, rating=5)
    unfair = Review.objects.create(proposal=abusive, brand=abusive.campaign.brand, creator=creator, rating=1, text="Hateful")
    recalculate_rating(creator.id)

    response = delete_with_reason(auth_client(admin), review_url(unfair.pk), "Abusive language.")

    assert response.status_code == 204
    profile = CreatorProfile.objects.get(user=creator)
    assert (profile.rating_count, str(profile.rating_avg)) == (1, "5.00")
    entry = AdminActionLog.objects.get()
    assert (entry.action, entry.target_type, entry.target_id) == ("review.remove", "review", unfair.pk)


def test_removing_the_only_review_resets_the_rating(admin, auth_client):
    proposal = ProposalFactory(status=Proposal.Status.ACCEPTED, completed_at=timezone.now())
    review = Review.objects.create(proposal=proposal, brand=proposal.campaign.brand, creator=proposal.creator, rating=2)
    recalculate_rating(proposal.creator_id)

    delete_with_reason(auth_client(admin), review_url(review.pk))

    profile = CreatorProfile.objects.get(user=proposal.creator)
    assert (profile.rating_count, profile.rating_avg) == (0, None)


def test_removing_an_unknown_review_is_404(admin, auth_client):
    assert delete_with_reason(auth_client(admin), review_url(999999)).status_code == 404


# ---- the action log ---------------------------------------------------------------------------------------------------------


def test_the_action_log_lists_newest_first(admin, auth_client):
    first, second = UserFactory(username="first"), UserFactory(username="second")
    client = auth_client(admin)
    client.post(user_url(first.pk, "suspend/"), {"reason": "one"}, format="json")
    client.post(user_url(second.pk, "suspend/"), {"reason": "two"}, format="json")

    rows = client.get(ACTIONS).json()["results"]

    assert [r["reason"] for r in rows] == ["two", "one"]
    assert rows[0]["admin"] == {"id": admin.id, "username": "root_admin"}
    assert rows[0]["target_label"] == "second" and rows[0]["action"] == "user.suspend"


# ---- the overview -------------------------------------------------------------------------------------------------------------


def test_overview_counts_users_campaigns_and_proposals(admin, auth_client):
    UserFactory(role=Role.CREATOR)
    UserFactory(role=Role.CREATOR, is_active=False)
    UserFactory(role=Role.BRAND)
    CampaignFactory(status=Campaign.Status.DRAFT)
    CampaignFactory(status=Campaign.Status.PUBLISHED)
    CampaignFactory(status=Campaign.Status.PUBLISHED)
    ProposalFactory()

    body = auth_client(admin).get(OVERVIEW).json()

    users = body["users"]
    assert users["by_role"]["creator"] >= 2 and users["by_role"]["brand"] >= 1 and users["by_role"]["admin"] == 1
    assert users["suspended"] == 1
    assert users["total"] == sum(users["by_role"].values())
    assert body["campaigns_by_status"] == {"draft": 1, "published": 3, "closed": 0}
    assert body["total_proposals"] == 1


def test_overview_signups_cover_the_last_30_days_with_zeros_filled_in(admin, auth_client):
    older = UserFactory()
    User.objects.filter(pk=older.pk).update(date_joined=timezone.now() - timedelta(days=5))
    ancient = UserFactory()
    User.objects.filter(pk=ancient.pk).update(date_joined=timezone.now() - timedelta(days=90))

    signups = auth_client(admin).get(OVERVIEW).json()["signups"]

    assert len(signups) == 30
    assert signups[-1]["date"] == timezone.now().date().isoformat()
    assert [s["date"] for s in signups] == sorted(s["date"] for s in signups)
    by_date = {s["date"]: s["count"] for s in signups}
    assert by_date[(timezone.now() - timedelta(days=5)).date().isoformat()] == 1
    assert sum(by_date.values()) == 2  # the admin (today) and the 5-day-old user; the 90-day-old one is outside the window


# ---- access -------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("role", [Role.CREATOR, Role.BRAND])
def test_ordinary_accounts_are_forbidden_everywhere_in_the_panel(db, auth_client, role):
    outsider = UserFactory(role=role)
    target = UserFactory()
    client = auth_client(outsider)

    assert client.get(USERS).status_code == 403
    assert client.get(ACTIONS).status_code == 403
    assert client.get(OVERVIEW).status_code == 403
    assert client.post(user_url(target.pk, "suspend/"), {"reason": REASON}, format="json").status_code == 403
    assert delete_with_reason(client, user_url(target.pk)).status_code == 403
    assert User.objects.get(pk=target.pk).is_active


def test_an_admin_login_does_not_expire_but_an_ordinary_login_lasts_a_day(admin, settings):
    from rest_framework_simplejwt.tokens import AccessToken

    from apps.accounts.services import issue_access_token

    def lifetime(user):
        token = AccessToken(issue_access_token(user))
        return token["exp"] - token["iat"]

    assert settings.ADMIN_TOKEN_MINUTES == 0
    assert lifetime(admin) == 10 * 365 * 24 * 3600  # ten years: no expiry in practice
    settings.ADMIN_TOKEN_MINUTES = 30  # a limit can still be set
    assert lifetime(admin) == 30 * 60
    assert lifetime(UserFactory(role=Role.CREATOR)) == 24 * 3600
    assert lifetime(UserFactory(role=Role.BRAND)) == 24 * 3600
