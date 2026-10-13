from apps.accounts.models import User

from .models import Kind, Notification


def notify(user: User, kind: str, message: str, **payload) -> Notification:
    """Create an in-app notification: the single entry point for every notification.

    ``payload`` becomes a JSON object, so pass only JSON-serialisable values (ids,
    strings, booleans). An unknown ``kind`` raises ``ValueError`` so typos fail loudly.
    """
    kind = Kind(kind)
    return Notification.objects.create(user=user, kind=kind, message=message, payload=payload)
