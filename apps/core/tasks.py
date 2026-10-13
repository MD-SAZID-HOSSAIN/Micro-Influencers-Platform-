import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, retry_backoff=True, retry_backoff_max=3600, retry_jitter=True)
def deliver_email(self, to: str, subject: str, body: str) -> None:
    """Send one email, retrying with backoff. Never raises: after the last retry it logs and gives up.

    An email failure must not affect the request that triggered it or the in-app notification.
    """
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            # Deliberately omit the body: it can contain one-time codes.
            logger.exception("Failed to send email (subject=%r) after %d retries", subject, self.max_retries)
            return
        logger.warning("Email send failed, will retry (subject=%r, attempt %d)", subject, self.request.retries + 1)
        raise self.retry(exc=exc)
