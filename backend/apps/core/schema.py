"""OpenAPI description of the session cookie authentication."""

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SessionCookieScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    target_class = "apps.core.authentication.SessionAuthentication"
    name = "sessionCookie"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        return {"type": "apiKey", "in": "cookie", "name": "__Host-session"}
