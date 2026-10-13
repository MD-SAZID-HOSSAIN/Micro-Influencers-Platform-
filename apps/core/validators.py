from urllib.parse import urlparse

from django.core.exceptions import ValidationError


def validate_safe_url(value: str) -> None:
    """Accept only absolute http(s) URLs; blocks javascript:, data:, ftp:, and //host."""
    parsed = urlparse(value or "")
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        raise ValidationError("Enter a valid http or https URL.", code="invalid_url")
