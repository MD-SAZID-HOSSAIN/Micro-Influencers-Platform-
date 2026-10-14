import pytest
from django.core.exceptions import ValidationError

from apps.core.validators import validate_safe_url


@pytest.mark.parametrize(
    "value",
    [
        "javascript:alert(1)",
        "data:text/html,x",
        "ftp://x.com",
        "//x.com",
        "https://",
        "example.com",
    ],
)
def test_validate_safe_url_rejects(value):
    with pytest.raises(ValidationError):
        validate_safe_url(value)


@pytest.mark.parametrize(
    "value", ["https://example.com/a?b=1", "http://example.com", "HTTPS://Example.com"]
)
def test_validate_safe_url_accepts(value):
    validate_safe_url(value)
