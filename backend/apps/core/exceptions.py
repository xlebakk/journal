"""API errors as stable machine codes: {"detail": "<code>"}; the frontend translates them.

Validation errors keep DRF's field → [messages] shape.
"""

from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class Conflict(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "conflict"
    default_code = "conflict"


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    # Django's own exceptions carry human messages ("No User matches…"): drop them.
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()
    response = drf_exception_handler(exc, context)
    if response is None or not isinstance(exc, exceptions.APIException):
        return response
    if isinstance(exc, exceptions.ValidationError):
        return response
    code = exc.get_codes()
    if isinstance(code, str):
        data: dict[str, Any] = {"detail": code}
        extra = getattr(exc, "extra", None)
        if extra:
            data.update(extra)
        response.data = data
    return response
