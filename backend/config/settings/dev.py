"""Local development. Never used in production."""

from config.env import env_list

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1", "api"])
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", ["http://localhost:5173"])
