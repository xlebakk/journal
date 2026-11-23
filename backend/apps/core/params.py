"""Query parameters parsed strictly: a malformed value is a 400, never a 500."""

import uuid
from datetime import date, time

from rest_framework.exceptions import ValidationError
from rest_framework.request import Request


def uuid_param(request: Request, name: str) -> uuid.UUID | None:
    value = request.query_params.get(name)
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ValidationError({name: ["invalid_id"]}) from exc


def date_param(request: Request, name: str) -> date | None:
    value = request.query_params.get(name)
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({name: ["invalid_date"]}) from exc


def time_param(request: Request, name: str) -> time | None:
    """«16:00» or «16:00:00»."""
    value = request.query_params.get(name)
    if not value:
        return None
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({name: ["invalid_time"]}) from exc
