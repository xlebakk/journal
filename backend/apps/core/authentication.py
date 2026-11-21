from rest_framework import authentication
from rest_framework.request import Request


class SessionAuthentication(authentication.SessionAuthentication):
    """Session auth that answers 401 (not 403) to anonymous requests.

    DRF only returns 401 when the authenticator provides a WWW-Authenticate value.
    """

    def authenticate_header(self, request: Request) -> str:
        return 'Session realm="api"'
