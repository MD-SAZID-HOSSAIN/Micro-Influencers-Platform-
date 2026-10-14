from drf_spectacular.extensions import OpenApiAuthenticationExtension


class VersionedJWTScheme(OpenApiAuthenticationExtension):
    """Documents VersionedJWTAuthentication as a Bearer JWT scheme in Swagger."""

    target_class = "apps.accounts.authentication.VersionedJWTAuthentication"
    name = "bearerAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
