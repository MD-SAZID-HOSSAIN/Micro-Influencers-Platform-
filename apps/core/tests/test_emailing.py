import logging
from smtplib import SMTPException
from unittest import mock

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


def test_deliver_email_task_is_registered_with_celery():
    from config.celery import app

    app.loader.import_default_modules()

    assert "apps.core.tasks.deliver_email" in app.tasks
