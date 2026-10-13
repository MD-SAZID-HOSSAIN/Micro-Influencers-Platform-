from django.db import transaction

from apps.accounts.models import User

from .emails import queue_notification_email, wants_email
from .models import Kind, Notification


def notify(user: User, kind: str, message: str, **payload) -> Notification:
    """Create an in-app notification: the single entry point for every notification.

    If the user has a verified address and notification emails on, the same event is also
    emailed once the surrounding transaction commits (a rolled-back event sends nothing).
    An email problem never affects the in-app notification.

    ``payload`` becomes a JSON object, so pass only JSON-serialisable values (ids,
    strings, booleans). An unknown ``kind`` raises ``ValueError`` so typos fail loudly.
    """
    kind = Kind(kind)
    notification = Notification.objects.create(user=user, kind=kind, message=message, payload=payload)
    if wants_email(user):
        transaction.on_commit(
            lambda: queue_notification_email(to=user.email, kind=kind, payload=payload)
        )
    return notification
