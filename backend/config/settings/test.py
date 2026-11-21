"""Test settings: same database engine as production, isolated in-memory cache."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-not-for-production")
os.environ.setdefault("DB_PASSWORD", "journal")

from .base import *  # noqa: F403

ALLOWED_HOSTS = ["testserver"]
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
