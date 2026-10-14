import logging

from django.template.loader import render_to_string

from . import tasks

logger = logging.getLogger(__name__)


def queue_email(to: str, subject: str, template: str, context: dict) -> None:
    """Render ``email/<template>.txt`` and send it in the background.

    Never raises: email trouble must not break the request that triggered it.
    """
    try:
        body = render_to_string(f"email/{template}.txt", context)
        tasks.deliver_email.delay(to, subject, body)
    except Exception:
        logger.exception("Failed to queue email (subject=%r, template=%r)", subject, template)
