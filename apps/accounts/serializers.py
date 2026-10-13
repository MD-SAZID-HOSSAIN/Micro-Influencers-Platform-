import re

from django.contrib.auth.validators import UnicodeUsernameValidator
from rest_framework import serializers

from apps.core.fields import SafeCharField

from .models import Role, User
from .services import register_user

_MOBILE_RE = re.compile(r"^\+?[0-9]{7,15}$")


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "full_name", "email", "username", "role", "mobile_number"]
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=[Role.CREATOR, Role.BRAND])
    full_name = SafeCharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    username = serializers.CharField(max_length=150, validators=[UnicodeUsernameValidator()])
    password = serializers.CharField(
        write_only=True, min_length=8, max_length=128, trim_whitespace=False
    )
    mobile_number = serializers.CharField(max_length=20)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_mobile_number(self, value):
        cleaned = re.sub(r"[\s\-()]", "", value)
        if not _MOBILE_RE.match(cleaned):
            raise serializers.ValidationError("Enter a valid mobile number.")
        return cleaned

    def create(self, validated_data):
        return register_user(**validated_data)
