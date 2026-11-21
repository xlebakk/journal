"""Walks every URL under /api/ and checks the deny-by-default rule.

* every API view is a DRF view with explicit permission classes;
* AllowAny appears only on the public allowlist;
* an anonymous request to any non-public endpoint gets 401.
"""

import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.permissions import AllowAny
from rest_framework.test import APIClient
from rest_framework.views import APIView

# URL names that may be reached without logging in. Keep this list short.
# The login flow (password, then the 2FA step) and health are the only public endpoints.
PUBLIC_URL_NAMES = {"health", "auth-login", "auth-totp"}

_CONVERTER_SAMPLES = {"int": "1", "uuid": str(uuid.uuid4()), "str": "x", "slug": "x", "path": "x"}
_PARAM_RE = re.compile(r"<(?:(?P<conv>\w+):)?(?P<name>\w+)>")


@dataclass
class Endpoint:
    url: str
    name: str | None
    view: Any


def _sample_url(route: str) -> str:
    return "/" + _PARAM_RE.sub(lambda m: _CONVERTER_SAMPLES[m.group("conv") or "str"], route)


def _walk(patterns: list[Any], prefix: str = "") -> Iterator[Endpoint]:
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from _walk(pattern.url_patterns, route)
        elif isinstance(pattern, URLPattern):
            yield Endpoint(_sample_url(route), pattern.name, pattern.callback)


def _api_endpoints() -> list[Endpoint]:
    return [e for e in _walk(get_resolver().url_patterns) if e.url.startswith("/api/")]


def _view_class(endpoint: Endpoint) -> type[APIView]:
    cls: type[APIView] | None = getattr(endpoint.view, "cls", None)
    message = f"{endpoint.url} is not a DRF view; API views must be DRF views with explicit rules"
    assert cls is not None, message
    assert issubclass(cls, APIView), message
    return cls


def _methods(endpoint: Endpoint, cls: type[APIView]) -> list[str]:
    actions = getattr(endpoint.view, "actions", None)
    if actions:
        return list(actions)
    return [m for m in cls.http_method_names if m != "options" and hasattr(cls, m)]


def test_api_has_endpoints() -> None:
    assert _api_endpoints(), "URL walker found no API endpoints; the walker itself is broken"


@pytest.mark.parametrize("endpoint", _api_endpoints(), ids=lambda e: e.url)
def test_permissions_are_explicit(endpoint: Endpoint) -> None:
    cls = _view_class(endpoint)
    permissions = list(cls.permission_classes)
    assert permissions, f"{endpoint.url} has no permission classes"
    if endpoint.name not in PUBLIC_URL_NAMES:
        assert AllowAny not in permissions, f"{endpoint.url} uses AllowAny but is not public"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "endpoint",
    [e for e in _api_endpoints() if e.name not in PUBLIC_URL_NAMES],
    ids=lambda e: e.url,
)
def test_anonymous_request_is_rejected_with_401(endpoint: Endpoint) -> None:
    client = APIClient()
    for method in _methods(endpoint, _view_class(endpoint)):
        response = getattr(client, method)(endpoint.url)
        assert response.status_code == 401, f"{method.upper()} {endpoint.url}"
