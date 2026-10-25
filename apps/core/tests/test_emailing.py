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


def test_retry_delay_never_drops_below_its_lower_bound_whatever_the_jitter():
    from apps.core.tasks import retry_delay

    with mock.patch("apps.core.tasks.random.uniform", return_value=0.7501):
        assert retry_delay(0) >= 0.75 * 30  # int() would round 22.5 down to 22
    with mock.patch("apps.core.tasks.random.uniform", return_value=1.0):
        assert retry_delay(0) == 30


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


def test_without_a_worker_a_failed_send_is_logged_with_its_reason_and_not_retried(settings, caplog):
    """Jobs that run inside the request (no worker, e.g. a free host) must not hold the request open with retries."""
    from apps.core.tasks import deliver_email

    settings.EMAIL_RETRY_ON_FAILURE = False
    with mock.patch("apps.core.tasks.send_mail", side_effect=SMTPException("535 authentication failed")) as send:
        with mock.patch.object(deliver_email, "retry") as retry:
            deliver_email.run("a@example.com", "Hi", "SECRET CODE 123456")

    assert send.call_count == 1 and retry.call_count == 0
    assert "SMTPException" in caplog.text and "535 authentication failed" in caplog.text
    assert "SECRET CODE" not in caplog.text  # the body can hold a one-time code
