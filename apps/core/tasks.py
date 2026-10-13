import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@shared_task
def deliver_email(to: str, subject: str, body: str) -> None:
    """Send one email. A provider failure is logged and never propagates."""
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
    except Exception:
        # Deliberately omit the body: it can contain one-time codes.
        logger.exception("Failed to send email (subject=%r)", subject)
