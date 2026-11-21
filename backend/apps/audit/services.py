"""Writing audit entries. Always inside the same transaction as the change itself."""

import uuid
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import connection
from django.db.models import Model
from rest_framework.request import Request

from apps.core.request_info import client_ip, user_agent

from .models import AuditLog

# Never copied into before/after, whatever the caller passes.
SECRET_FIELDS = frozenset({"password", "totp_secret", "totp_last_counter", "code_hash", "key_hash"})


def _plain(value: Any) -> Any:
    if isinstance(value, uuid.UUID | Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items() if k not in SECRET_FIELDS}
    if isinstance(value, list | tuple | set):
        return [_plain(v) for v in value]
    return value


def snapshot(instance: Model, fields: Iterable[str]) -> dict[str, Any]:
    """Field values of a model instance, ready for before/after."""
    result = {name: getattr(instance, name) for name in fields if name not in SECRET_FIELDS}
    return _plain(result)  # type: ignore[no-any-return]


def record(
    *,
    request: Request | None,
    action: str,
    entity: Model | None = None,
    entity_type: str = "",
    entity_id: str = "",
    before: Mapping[str, Any] | None = None,
    after: Mapping[str, Any] | None = None,
    reason: str = "",
) -> AuditLog:
    if not connection.in_atomic_block:
        raise RuntimeError("audit.record() must run inside transaction.atomic()")
    actor = None
    actor_role = ""
    if request is not None and request.user.is_authenticated:
        actor = request.user
        actor_role = request.session.get("active_role", "")
    if entity is not None:
        entity_type = entity_type or entity._meta.label_lower
        entity_id = entity_id or str(entity.pk)
    return AuditLog.objects.create(
        actor=actor,
        actor_role=actor_role,
        ip=client_ip(request) if request is not None else None,
        user_agent=user_agent(request) if request is not None else "",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=_plain(before) if before is not None else None,
        after=_plain(after) if after is not None else None,
        reason=reason,
    )
