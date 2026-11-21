"""OpenAPI description of the authentication: the site's session cookie, the app's Bearer token."""

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SessionCookieScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    target_class = "apps.core.authentication.SessionAuthentication"
    name = "sessionCookie"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        return {"type": "apiKey", "in": "cookie", "name": "__Host-session"}


class AppBearerScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    """The Android app: a 10-minute access token from /auth/token (stage 6)."""

    target_class = "apps.core.authentication.AppTokenAuthentication"
    name = "appBearer"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        return {"type": "http", "scheme": "bearer"}
