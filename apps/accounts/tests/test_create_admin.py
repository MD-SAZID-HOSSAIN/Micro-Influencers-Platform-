from io import StringIO
from unittest import mock

import pytest
from django.core.management import CommandError, call_command

from apps.accounts.models import Role, User

GETPASS = "apps.accounts.management.commands.create_admin.getpass"


def run(*args, passwords=("Tr0ub4dor&3-Horse", "Tr0ub4dor&3-Horse")):
    out = StringIO()
    with mock.patch(GETPASS, side_effect=list(passwords)):
        call_command("create_admin", *args, stdout=out)
    return out.getvalue()


def test_creates_an_admin_with_the_prompted_password(db):
    run("--email", "root@example.com", "--username", "root", "--full-name", "Root Admin")

    admin = User.objects.get(username="root")
    assert admin.role == Role.ADMIN
    assert admin.email == "root@example.com" and admin.full_name == "Root Admin"
    assert admin.check_password("Tr0ub4dor&3-Horse")
    assert admin.is_active is True


def test_the_password_is_never_echoed_or_accepted_as_an_argument(db):
    output = run("--email", "root@example.com", "--username", "root")

    assert "Tr0ub4dor&3-Horse" not in output
    with pytest.raises(CommandError):  # there is simply no --password option
        call_command("create_admin", "--email", "a@example.com", "--username", "a", "--password", "x")


def test_mismatched_passwords_create_nothing(db):
    with pytest.raises(CommandError, match="match"):
        run("--email", "root@example.com", "--username", "root", passwords=("Tr0ub4dor&3-Horse", "different1!-different"))

    assert not User.objects.exists()


def test_short_passwords_are_refused(db):
    with pytest.raises(CommandError, match="12"):
        run("--email", "root@example.com", "--username", "root", passwords=("Short-1!", "Short-1!"))

    assert not User.objects.exists()


@pytest.mark.parametrize(
    "weak",
    [
        "12345678901234",  # only digits
        "rootadministrator",  # looks like the username
        "password123456",  # one of the most common passwords
    ],
)
def test_easy_to_guess_passwords_are_refused(db, weak):
    with pytest.raises(CommandError):
        run("--email", "root@example.com", "--username", "rootadministrator", passwords=(weak, weak))

    assert not User.objects.exists()


def test_duplicate_email_or_username_is_refused(db):
    run("--email", "root@example.com", "--username", "root")

    with pytest.raises(CommandError, match="already"):
        run("--email", "ROOT@example.com", "--username", "other")
    with pytest.raises(CommandError, match="already"):
        run("--email", "other@example.com", "--username", "Root")
    assert User.objects.count() == 1


def test_an_invalid_email_is_refused(db):
    with pytest.raises(CommandError, match="email"):
        run("--email", "not-an-email", "--username", "root")


def test_the_admin_can_log_in_to_the_panel_but_registration_still_cannot_create_one(db):
    from rest_framework.test import APIClient

    run("--email", "root@example.com", "--username", "root")
    client = APIClient()

    panel = client.post("/api/v1/admin/auth/login/", {"identifier": "root", "password": "Tr0ub4dor&3-Horse"}, format="json")
    register = client.post(
        "/api/v1/auth/register/",
        {
            "role": "admin",
            "full_name": "Evil",
            "email": "evil@example.com",
            "username": "evil",
            "password": "Tr0ub4dor&3-Horse",
            "mobile_number": "+8801712345678",
        },
        format="json",
    )

    assert panel.status_code == 200
    assert register.status_code == 400
