from django.utils.html import strip_tags
from rest_framework import serializers
from rest_framework.fields import empty

from .validators import validate_safe_url


class SafeCharField(serializers.CharField):
    """CharField that strips HTML tags and surrounding whitespace from input."""

    def to_internal_value(self, data):
        value = strip_tags(super().to_internal_value(data)).strip()
        if value == "" and not self.allow_blank:
            self.fail("blank")
        return value


class OptionalUrlField(serializers.CharField):
    """An optional http(s) URL. Blank or null input is stored as ``None``."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 500)
        kwargs.setdefault("allow_blank", True)
        kwargs.setdefault("allow_null", True)
        kwargs.setdefault("required", False)
        super().__init__(**kwargs)
        self.validators.append(validate_safe_url)

    def run_validation(self, data=empty):
        value = super().run_validation(data)
        return None if value in ("", None) else value
