import pytest
from rest_framework import serializers

from apps.core.fields import SafeCharField


def test_safe_char_field_strips_tags():
    assert SafeCharField().run_validation("<script>x</script>hi") == "xhi"


def test_safe_char_field_trims_whitespace():
    assert SafeCharField().run_validation("  hello  ") == "hello"


def test_safe_char_field_rejects_input_that_is_only_markup():
    with pytest.raises(serializers.ValidationError):
        SafeCharField().run_validation("<b></b>")


def test_safe_char_field_allows_blank_when_configured():
    assert SafeCharField(allow_blank=True).run_validation("<b></b>") == ""
