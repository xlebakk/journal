"""Test settings: same database engine as production, isolated in-memory cache."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-not-for-production")
os.environ.setdefault("DB_PASSWORD", "journal")
# Test-only Fernet key (base64 of 32 zero-ish bytes); never used outside tests.
os.environ.setdefault("TOTP_ENCRYPTION_KEYS", "dGVzdC1vbmx5LWtleS10ZXN0LW9ubHkta2V5LTAwMDA=")

from .base import *  # noqa: F403

ALLOWED_HOSTS = ["testserver"]
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Throttling is tested explicitly where it matters (login limits use their own counters).
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}  # noqa: F405
