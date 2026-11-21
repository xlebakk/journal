# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /usr/local/bin/uv
RUN groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app
COPY pyproject.toml uv.lock ./

# --- Development: dependencies with dev tools; code is mounted as a volume.
FROM base AS dev
RUN uv sync --frozen --no-install-project
USER app
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:8000"]

# --- Production: no dev tools, non-root, gunicorn, read-only root filesystem in compose.
FROM base AS prod
RUN uv sync --frozen --no-dev --no-install-project
COPY --chown=app:app . .
# The logo lives in a volume mounted here; an empty volume takes this owner.
RUN mkdir -p /app/media && chown app:app /app/media
ENV DJANGO_SETTINGS_MODULE=config.settings.prod
USER app
EXPOSE 8000
# Access log as JSON without the query string (SPEC §11: no tokens or personal data in logs).
# No control socket: the root filesystem is read-only, and restarts go through Docker.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", \
     "--worker-tmp-dir", "/dev/shm", "--no-control-socket", "--access-logfile", "-", \
     "--access-logformat", "{\"time\": \"%(t)s\", \"method\": \"%(m)s\", \"path\": \"%(U)s\", \"status\": %(s)s, \"ms\": %(M)s}"]
