from typing import Any

from rest_framework import authentication
from rest_framework.request import Request


class SessionAuthentication(authentication.SessionAuthentication):
    """Session auth that answers 401 (not 403) to anonymous requests.

    DRF only returns 401 when the authenticator provides a WWW-Authenticate value.
    """

    def authenticate_header(self, request: Request) -> str:
        return 'Session realm="api"'


class AppTokenAuthentication(authentication.BaseAuthentication):
    """Bearer requests of the Android app, already checked by AppTokenMiddleware.

    No CSRF check: the token travels in a header that a third-party page cannot set.
    """

    def authenticate(self, request: Request) -> tuple[Any, Any] | None:
        session = getattr(request._request, "app_session", None)
        if session is None:
            return None
        return session.user, session

    def authenticate_header(self, request: Request) -> str:
        return 'Bearer realm="api"'
