# Электронный журнал учебного центра

Группы, ученики, расписание, оценки, посещаемость и пробные тесты. Три роли: администратор, преподаватель, ученик. Веб (PWA) и Android из одной кодовой базы.

ТЗ — [SPEC.md](SPEC.md). Соглашения — [CLAUDE.md](CLAUDE.md). Решения — [docs/decisions.md](docs/decisions.md). Безопасность — [docs/security.md](docs/security.md).

**Статус:** этап 0 (фундамент) готов. Вход и пользователи появятся на этапе 1.

## Запуск за 5 команд

Нужны Git и Docker Desktop (или Docker Engine с Compose v2).

```sh
git clone <адрес репозитория> journal && cd journal
cp .env.example .env            # замените все change-me на свои значения
docker compose -f infra/docker-compose.dev.yml up --build
# фронтенд: http://localhost:5173 · стайлгайд: http://localhost:5173/dev/styleguide
# API:      http://localhost:5173/api/v1/health → {"status": "ok"}
```

В `.env` пароль Redis указывается дважды: в `REDIS_PASSWORD` и внутри `REDIS_URL`. Значения должны совпадать.

## Разработка без Docker

Нужны PostgreSQL 16+, Redis 7+, [uv](https://docs.astral.sh/uv/) и Node 22+.

```sh
cd backend && uv sync && uv run python manage.py migrate && uv run python manage.py runserver
cd frontend && npm ci && npm run dev
```

Переменные окружения те же, что в `.env.example`; для локальной базы — `DB_HOST=localhost`, `REDIS_URL=redis://:пароль@localhost:6379/0`.

## Проверки

```sh
cd backend  && uv run pytest && uv run ruff check . && uv run mypy . && uv run bandit -q -c pyproject.toml -r apps config && uv run pip-audit
cd frontend && npm test && npm run lint && npm run typecheck && npm run contrast && npm run build && npm audit
uv run --project backend pre-commit run --all-files
```

Всё это же запускает CI (`.github/workflows/ci.yml`) на каждый push и pull request.
