"""Production. Runs behind Caddy, which terminates TLS and sets the security headers."""

from .base import *  # noqa: F403

DEBUG = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
# Internal container healthchecks talk plain HTTP.
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health$"]
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Structured logs on stdout; Docker keeps and rotates them.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "apps.core.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        # 4xx answers are expected traffic, not incidents.
        "django.request": {"level": "ERROR"},
        "django.security.DisallowedHost": {"level": "ERROR"},
    },
}
