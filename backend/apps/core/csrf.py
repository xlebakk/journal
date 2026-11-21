from typing import Any

from django.middleware.csrf import CsrfViewMiddleware
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request


class _Check(CsrfViewMiddleware):
    def _reject(self, request: Any, reason: str) -> Any:
        return reason


def enforce_csrf(request: Request) -> None:
    """CSRF check for views that anonymous users POST to (login, 2FA step).

    DRF checks CSRF only for already authenticated sessions; login must be protected too.
    """
    django_request = request._request
    check = _Check(lambda _: None)  # type: ignore[arg-type]
    check.process_request(django_request)
    reason = check.process_view(django_request, lambda: None, (), {})  # type: ignore[arg-type, return-value]
    if reason:
        raise PermissionDenied(detail="csrf_failed", code="csrf_failed")


class CsrfEnforcedMixin:
    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)  # type: ignore[misc]
        if request.method not in ("GET", "HEAD", "OPTIONS", "TRACE"):
            enforce_csrf(request)
