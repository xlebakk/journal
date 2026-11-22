"""Records refused API requests of logged-in users for the overview (stage 7)."""

import logging
from collections.abc import Callable

from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse

from apps.accounts import sessions
from apps.accounts.models import User
from apps.core.request_info import client_ip

from .models import DeniedRequest

log = logging.getLogger(__name__)

# Only a refusal to show or do something counts — not «enter your password again», not a
# business rule such as a closed edit window.
COUNTED = {403: "permission_denied", 404: "not_found"}


class DeniedRequestMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        code = COUNTED.get(response.status_code)
        if code is None or not request.path_info.startswith("/api/"):
            return response
        user = request.user
        if not (user.is_authenticated and isinstance(user, User)):
            return response
        data = getattr(response, "data", None)
        if not isinstance(data, dict) or data.get("detail") != code:
            return response
        try:
            DeniedRequest.objects.create(
                user=user,
                role=sessions.get_active_role(request) or "",
                ip=client_ip(request),
                method=request.method or "",
                path=request.path_info[:200],
                status=response.status_code,
            )
        except DatabaseError:
            # Monitoring must never break the answer itself.
            log.exception("could not record a denied request")
        return response
