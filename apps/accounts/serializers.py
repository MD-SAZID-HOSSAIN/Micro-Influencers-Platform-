import re

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.core.fields import SafeCharField

from .models import Role, User
from .services import register_user

_MOBILE_RE = re.compile(r"^\+?[0-9]{7,15}$")


def check_password_strength(password: str, user: User | None = None) -> None:
    """Run Django's password validators (too common, all digits, too like the username or email)."""
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages))


class UserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField(
        help_text="The creator's photo or the brand's logo, if they have one."
    )

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "email",
            "username",
            "role",
            "mobile_number",
            "email_verified",
            "avatar_url",
        ]
        read_only_fields = fields

    def get_avatar_url(self, user) -> str | None:
        try:
            if user.role == Role.CREATOR:
                return user.creator_profile.photo_url
            if user.role == Role.BRAND:
                return user.brand_profile.logo_url
        except ObjectDoesNotExist:
            pass
        return None


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(help_text="Email or username")
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class LoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    user = UserSerializer()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.RegexField(
        r"^\d{6}$", error_messages={"invalid": "Enter the 6-digit code."}
    )
    new_password = serializers.CharField(
        write_only=True, min_length=8, max_length=128, trim_whitespace=False
    )

    def validate_new_password(self, value):
        check_password_strength(value)
        return value


class EmailVerifySerializer(serializers.Serializer):
    code = serializers.RegexField(
        r"^\d{6}$", error_messages={"invalid": "Enter the 6-digit code."}
    )


class NotificationSettingsSerializer(serializers.ModelSerializer):
    email_enabled = serializers.BooleanField(source="email_notifications_enabled")
    email_verified = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ["email_enabled", "email_verified"]


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


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

    def validate(self, attrs):
        # Checked last, with the other fields in hand, so a password that is just the username fails.
        try:
            check_password_strength(
                attrs["password"],
                User(username=attrs["username"], email=attrs["email"], full_name=attrs["full_name"]),
            )
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({"password": exc.detail})
        return attrs

    def create(self, validated_data):
        return register_user(**validated_data)
