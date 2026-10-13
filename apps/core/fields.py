from django.utils.html import strip_tags
from rest_framework import serializers


class SafeCharField(serializers.CharField):
    """CharField that strips HTML tags and surrounding whitespace from input."""

    def to_internal_value(self, data):
        value = strip_tags(super().to_internal_value(data)).strip()
        if value == "" and not self.allow_blank:
            self.fail("blank")
        return value
