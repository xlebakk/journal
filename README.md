# Электронный журнал учебного центра

Группы, ученики, расписание, оценки, посещаемость и пробные тесты. Три роли: администратор, преподаватель, ученик. Веб (PWA) и Android из одной кодовой базы.

ТЗ — [SPEC.md](SPEC.md). Соглашения — [CLAUDE.md](CLAUDE.md). Решения — [docs/decisions.md](docs/decisions.md). Безопасность и матрица прав — [docs/security.md](docs/security.md).

**Статус:** этапы 0 (фундамент) и 1 (вход и пользователи) готовы.

- Вход с определением роли.
- 2FA для администратора, принудительная смена временного пароля.
- Сеансы с тайм-аутами по ролям и их отзыв, блокировки попыток входа.
- Аудит и журнал входов.
- Управление пользователями для администратора.

Группы и расписание появятся на этапе 2.

## Запуск за 5 команд

Нужны Git и Docker Desktop (или Docker Engine с Compose v2).

```sh
git clone <адрес репозитория> journal && cd journal
cp .env.example .env            # замените все change-me на свои значения
docker compose -f infra/docker-compose.dev.yml up --build
docker compose -f infra/docker-compose.dev.yml exec api python manage.py seed_demo
# откройте http://localhost:5173 и войдите логином и паролем из вывода seed_demo
```

Пароль Redis в `.env` указывается дважды: в `REDIS_PASSWORD` и внутри `REDIS_URL`, значения должны совпадать. `TOTP_ENCRYPTION_KEYS` — ключ Fernet, команда генерации есть в `.env.example`.

## Демо-данные

`seed_demo` создаёт 1 администратора, 6 преподавателей и 60 учеников и печатает их логины и пароли. Команда работает только в разработке (`DEBUG=True`) и только на пустой базе.

1. Войдите администратором. При первом входе нужно настроить 2FA: отсканируйте QR-код в Google Authenticator или Aegis.
2. Сохраните резервные коды.
3. Проверьте три роли (SPEC, «Как пользоваться», п. 6):
   - ученик попадает на `/student`, а по адресу `/admin/users` видит «Страница не найдена» (API отвечает 403);
   - преподаватель попадает на `/teacher` и тоже не видит админских разделов;
   - администратор в разделе «Пользователи» создаёт человека и получает временный пароль. Пароль показывается один раз, при первом входе с ним открывается только смена пароля.

## Разработка без Docker

Нужны PostgreSQL 16+ (с ICU- или UTF-8-локалью, не `C`), Redis 7+, [uv](https://docs.astral.sh/uv/) и Node 22+.

```sh
cd backend && uv sync && uv run python manage.py migrate && uv run python manage.py runserver
cd frontend && npm ci && npm run dev
```

Переменные окружения те же, что в `.env.example`. Для локальной базы: `DB_HOST=localhost`, `REDIS_URL=redis://:пароль@localhost:6379/0`.

## Проверки

```sh
cd backend  && uv run pytest --cov && uv run ruff check . && uv run mypy . && uv run bandit -q -c pyproject.toml -r apps config && uv run pip-audit
cd frontend && npm test && npm run lint && npm run typecheck && npm run contrast && npm run build && npm audit
uv run --project backend pre-commit run --all-files
```

**e2e (Playwright).** Нужен PostgreSQL с пустой базой `journal_e2e`, Redis не нужен. Playwright сам поднимает Django на `:8001` и Vite на `:5174`, перед каждым прогоном пересоздаёт базу и проходит сценарии: вход каждой ролью, 2FA, создание пользователя, принудительная смена пароля.

```sh
cd frontend && npx playwright install chromium && npm run e2e
```

**API-типы.** После изменения API перегенерируйте схему и типы, CI сверяет оба файла:

```sh
cd backend && uv run python manage.py spectacular --settings=config.settings.test --file ../frontend/src/shared/api/schema.yml
cd frontend && npm run api:types
```

Всё это же запускает CI (`.github/workflows/ci.yml`) на каждый push и pull request.
