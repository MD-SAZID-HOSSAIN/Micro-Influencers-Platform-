import pytest
from rest_framework import serializers

from apps.core.fields import OptionalUrlField, SafeCharField


def test_optional_url_field_turns_blank_and_null_into_none():
    field = OptionalUrlField()

    assert field.run_validation("") is None
    assert field.run_validation(None) is None


def test_optional_url_field_accepts_https_and_rejects_script_urls():
    field = OptionalUrlField()

    assert field.run_validation(" https://example.com/a.png ") == "https://example.com/a.png"
    with pytest.raises(serializers.ValidationError):
        field.run_validation("javascript:alert(1)")


def test_safe_char_field_strips_tags():
    assert SafeCharField().run_validation("<script>x</script>hi") == "xhi"


def test_safe_char_field_trims_whitespace():
    assert SafeCharField().run_validation("  hello  ") == "hello"


def test_safe_char_field_rejects_input_that_is_only_markup():
    with pytest.raises(serializers.ValidationError):
        SafeCharField().run_validation("<b></b>")


def test_safe_char_field_allows_blank_when_configured():
    assert SafeCharField(allow_blank=True).run_validation("<b></b>") == ""
