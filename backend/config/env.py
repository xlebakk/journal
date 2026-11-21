"""Reading settings from environment variables.

Secrets come only from the environment (`.env` in development is loaded by Docker Compose).
"""

import os

from django.core.exceptions import ImproperlyConfigured

_MISSING = object()


def env_str(name: str, default: str | object = _MISSING) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        if default is _MISSING:
            raise ImproperlyConfigured(f"Environment variable {name} is required")
        return str(default)
    return value


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    if value.lower() in {"1", "true", "yes", "on"}:
        return True
    if value.lower() in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"Environment variable {name} must be a boolean, got {value!r}")


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ImproperlyConfigured(f"Environment variable {name} must be an integer") from exc


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    value = os.environ.get(name)
    if value is None or value == "":
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]
