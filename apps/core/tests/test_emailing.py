import logging
from smtplib import SMTPException
from unittest import mock

import pytest

from django.core import mail

from apps.core.emailing import queue_email


def test_queue_email_sends_via_backend():
    queue_email(
        "amina@example.com",
        "Your password reset code",
        "password_reset",
        {"code": "123456", "expires_minutes": 10},
    )

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["amina@example.com"]
    assert message.subject == "Your password reset code"
    assert "123456" in message.body
    assert "10 minutes" in message.body


def test_provider_failure_is_logged_not_raised(caplog):
    with mock.patch("apps.core.tasks.send_mail", side_effect=SMTPException("provider down")):
        with caplog.at_level(logging.ERROR):
            queue_email(
                "amina@example.com",
                "Your password reset code",
                "password_reset",
                {"code": "654321", "expires_minutes": 10},
            )

    assert "Failed to send email" in caplog.text
    assert mail.outbox == []


def test_secret_code_never_appears_in_logs(caplog):
    with mock.patch("apps.core.tasks.send_mail", side_effect=SMTPException("provider down")):
        with caplog.at_level(logging.DEBUG):
            queue_email(
                "amina@example.com",
                "Your password reset code",
                "password_reset",
                {"code": "654321", "expires_minutes": 10},
            )

    assert "654321" not in caplog.text


def test_queue_email_swallows_broker_error(caplog):
    with mock.patch("apps.core.tasks.deliver_email.delay", side_effect=ConnectionError("redis down")):
        with caplog.at_level(logging.ERROR):
            queue_email("amina@example.com", "Hi", "password_reset", {"code": "1", "expires_minutes": 10})

    assert "Failed to queue email" in caplog.text


def test_unknown_template_is_logged_not_raised(caplog):
    with caplog.at_level(logging.ERROR):
        queue_email("amina@example.com", "Hi", "no_such_template", {})

    assert mail.outbox == []
    assert "Failed to queue email" in caplog.text


def test_retry_delays_grow_exponentially_and_are_capped():
    from apps.core.tasks import retry_delay

    for retries in range(6):
        base = 30 * 2**retries
        assert 0.75 * base <= retry_delay(retries) <= base  # jitter spreads retries out a little
    assert retry_delay(20) <= 3600  # never longer than an hour


def test_a_failed_send_schedules_its_retry_with_the_backoff_delay():
    """Celery only applies retry_backoff to autoretry; a manual retry needs an explicit countdown."""
    from celery.exceptions import Retry

    from apps.core.tasks import deliver_email

    deliver_email.push_request(retries=3)
    try:
        with mock.patch("apps.core.tasks.send_mail", side_effect=SMTPException("down")):
            with mock.patch.object(deliver_email, "retry", side_effect=Retry()) as retry:
                with pytest.raises(Retry):
                    deliver_email.run("a@example.com", "Hi", "Body")
    finally:
        deliver_email.pop_request()

    countdown = retry.call_args.kwargs["countdown"]
    assert 0.75 * 240 <= countdown <= 240  # the fourth attempt waits about 4 minutes, not a fixed 3


def test_deliver_email_task_is_registered_with_celery():
    from config.celery import app

    app.loader.import_default_modules()

    assert "apps.core.tasks.deliver_email" in app.tasks
