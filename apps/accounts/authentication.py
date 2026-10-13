from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class VersionedJWTAuthentication(JWTAuthentication):
    """JWT auth that also rejects tokens issued before the user's last token_version bump."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)  # also rejects missing/inactive users
        if validated_token.get("tv") != user.token_version:
            raise AuthenticationFailed("Token is no longer valid.", code="token_not_valid")
        return user
