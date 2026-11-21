"""End-to-end tests (Playwright): dev settings on a throwaway database, no Redis needed.

Never used in production; `seed_e2e` wipes this database on every run.
"""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "e2e-only-secret-key-not-for-production")
os.environ.setdefault("TOTP_ENCRYPTION_KEYS", "ZTJlLW9ubHkta2V5LWUyZS1vbmx5LWtleS0wMDAwMDA=")
os.environ.setdefault("DB_PASSWORD", "journal")

from .dev import *  # noqa: F403

DATABASES["default"]["NAME"] = os.environ.get("E2E_DB_NAME", "journal_e2e")  # noqa: F405
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:5174"]
# The whole Playwright suite logs in ~20 times from 127.0.0.1 within minutes; the per-IP limit
# itself is covered by unit tests, so here it must not make the run depend on timing.
LOGIN_IP_LIMIT = 1000
