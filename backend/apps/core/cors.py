"""CORS for the Android app (stage 6). The browser site is same-origin and needs none.

Only the Capacitor WebView origins from `APP_ORIGINS` are allowed, only for /api/, and never
with credentials: the app authenticates with a Bearer header, so cookies are not involved.
"""

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

ALLOWED_METHODS = "GET, POST, PUT, PATCH, DELETE"
ALLOWED_HEADERS = "Authorization, Content-Type, Accept"


class AppCorsMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        origin = request.headers.get("Origin") or ""
        allowed = origin in settings.APP_ORIGINS and request.path_info.startswith("/api/")
        preflight = request.method == "OPTIONS" and "Access-Control-Request-Method" in (
            request.headers
        )
        if allowed and preflight:
            response = HttpResponse(status=204)
            response["Access-Control-Allow-Methods"] = ALLOWED_METHODS
            response["Access-Control-Allow-Headers"] = ALLOWED_HEADERS
            response["Access-Control-Max-Age"] = "600"
        else:
            response = self.get_response(request)
        if allowed:
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Expose-Headers"] = "Content-Disposition, Retry-After"
        response.headers.setdefault("Vary", "Origin")
        return response
