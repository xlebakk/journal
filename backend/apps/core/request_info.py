"""Client IP and user agent, safe for logging."""

import ipaddress

from django.conf import settings
from django.http import HttpRequest
from rest_framework.request import Request


def client_ip(request: HttpRequest | Request) -> str | None:
    """REMOTE_ADDR, or the address Caddy put into X-Forwarded-For when behind it.

    Only the last TRUSTED_PROXY_COUNT hops are trusted, so the client cannot spoof it.
    """
    meta = request.META
    ip = meta.get("REMOTE_ADDR", "")
    hops = settings.TRUSTED_PROXY_COUNT
    if hops:
        forwarded = [
            p.strip() for p in meta.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()
        ]
        if len(forwarded) >= hops:
            ip = forwarded[-hops]
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return None


def user_agent(request: HttpRequest | Request) -> str:
    return str(request.META.get("HTTP_USER_AGENT", ""))[:300]
