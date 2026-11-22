"""Login attempt limits, kept in the cache (Redis in production).

* per login: N failures → lock for base minutes; every next lock doubles, up to max hours.
  Counters are keyed by the login string, so non-existent logins lock exactly the same way;
* per IP: at most LOGIN_IP_LIMIT attempts per LOGIN_IP_WINDOW_SECONDS.
"""

import hashlib
import math
import time

from django.conf import settings
from django.core.cache import cache

from apps.core.models import CenterSettings

from .models import normalize_login

_DAY = 24 * 3600


def _key(kind: str, login: str) -> str:
    digest = hashlib.sha256(normalize_login(login).encode()).hexdigest()[:32]
    return f"auth:{kind}:{digest}"


def _incr(key: str, ttl: int) -> int:
    cache.add(key, 0, ttl)
    try:
        return int(cache.incr(key))
    except ValueError:  # expired between add and incr
        cache.set(key, 1, ttl)
        return 1


def locked_seconds(login: str) -> int:
    """Seconds until the login may be tried again; 0 if not locked."""
    until = cache.get(_key("lock", login))
    if until is None:
        return 0
    return max(0, math.ceil(float(until) - time.time()))


def register_failure(login: str) -> int:
    """Count a failure. Returns the lock duration in seconds if this failure locks, else 0."""
    policy = CenterSettings.load()
    failures = _incr(_key("fail", login), _DAY)
    if failures < policy.lockout_threshold:
        return 0
    cache.delete(_key("fail", login))
    level = _incr(_key("level", login), 2 * _DAY)
    minutes = policy.lockout_base_minutes << (level - 1)
    seconds = min(minutes * 60, policy.lockout_max_hours * 3600)
    cache.set(_key("lock", login), time.time() + seconds, seconds)
    return seconds


def reset_failures(login: str) -> None:
    """After a successful login. The escalation level stays until it expires."""
    cache.delete(_key("fail", login))


def clear(login: str) -> None:
    """Administrator unlocks the account."""
    cache.delete_many([_key("fail", login), _key("lock", login), _key("level", login)])


def ip_over_limit_seconds(ip: str | None) -> int:
    """Count an attempt from this IP. Returns seconds to wait if over the limit, else 0."""
    if not ip:
        return 0
    window = settings.LOGIN_IP_WINDOW_SECONDS
    now = time.time()
    bucket = int(now // window)
    attempts = _incr(f"auth:ip:{ip}:{bucket}", window)
    if attempts <= settings.LOGIN_IP_LIMIT:
        return 0
    return max(1, math.ceil((bucket + 1) * window - now))


def minutes(seconds: int) -> int:
    return max(1, math.ceil(seconds / 60))
