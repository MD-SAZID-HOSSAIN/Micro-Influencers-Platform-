import logging
import math
import random

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
BASE_DELAY_SECONDS = 30
MAX_DELAY_SECONDS = 3600


def retry_delay(retries: int) -> int:
    """Seconds to wait before the next attempt: 30, 60, 120, 240, 480... capped at an hour.

    Up to 25% is shaved off at random so a provider outage does not make every queued email
    retry at the same instant.
    """
    base = min(BASE_DELAY_SECONDS * 2**retries, MAX_DELAY_SECONDS)
    return math.ceil(base * random.uniform(0.75, 1.0))


@shared_task(bind=True, max_retries=MAX_RETRIES)
def deliver_email(self, to: str, subject: str, body: str) -> None:
    """Send one email, retrying with exponential backoff. Never raises to its caller.

    After the last retry it logs the failure and gives up: an email problem must not affect the
    request that triggered it or the in-app notification. (Celery's ``retry_backoff`` option only
    applies to automatic retries, so the delay is passed to ``retry`` explicitly.)
    """
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
    except Exception as exc:
        if not settings.EMAIL_RETRY_ON_FAILURE:
            # No worker is waiting to retry later (the job runs inside the request), and retrying at once would only
            # hold the request open. Say why it failed so the host's log shows a wrong login or sender.
            logger.error("Failed to send email (subject=%r): %s: %s", subject, type(exc).__name__, exc)
            return
        if self.request.retries >= self.max_retries:
            # Deliberately omit the body: it can contain one-time codes.
            logger.exception("Failed to send email (subject=%r) after %d retries", subject, self.max_retries)
            return
        logger.warning("Email send failed, will retry (subject=%r, attempt %d)", subject, self.request.retries + 1)
        raise self.retry(exc=exc, countdown=retry_delay(self.request.retries))
