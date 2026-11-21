# CLAUDE.md — соглашения проекта

Электронный журнал учебного центра. Полное ТЗ — [SPEC.md](SPEC.md), журнал решений — [docs/decisions.md](docs/decisions.md), матрица прав — [docs/security.md](docs/security.md).

## Как работаем

- Один этап (SPEC §14) — одна ветка `stage-N`. Этап закрыт, когда тесты зелёные, README обновлён, изменения закоммичены и функцию можно показать на демо-данных.
- Решение, которое легко переделать, — выбираем простейшее и пишем в `docs/decisions.md` («дата · решение · почему»). Дорогое (схема БД, права, формулы оценок) — сначала спрашиваем.
- Новая зависимость — одна строка обоснования в `docs/decisions.md`. Версии фиксируются lock-файлами (`backend/uv.lock`, `frontend/package-lock.json`), во фронтенде — `--save-exact`.
- Интерфейс на русском, все строки — в `frontend/src/shared/i18n/ru.json`. Идентификаторы в коде — по-английски.

## Структура

```
backend/            Django 5.2 LTS + DRF, Python 3.13, uv
  config/settings/  base · dev · test · prod; секреты только из окружения (config/env.py)
  apps/core/        общее: health, SessionAuthentication с 401, обработчики 404/500
  apps/accounts/    пользователи (AUTH_USER_MODEL = accounts.User, UUID)
  apps/<остальные>/ academics, schedule, journal, exams, reports, announcements, audit — создаются на своих этапах
frontend/           React + TypeScript + Vite, CSS Modules, TanStack Query, React Router
  src/app/          роутинг, лэйауты
  src/features/     auth, student, teacher, admin
  src/shared/ui/    свои компоненты; tokens.css — единственное место с цветами и размерами
  src/shared/api/   сгенерированный из OpenAPI клиент
  src/dev/          /dev/styleguide (только в dev-сборке)
infra/              docker-compose, init-скрипты БД, позже Caddyfile и бэкапы
mobile/             Capacitor (этап 6)
docs/               decisions.md, security.md, позже deploy.md, admin-guide.md
```

## Команды

| Что | Команда |
| --- | --- |
| Весь стек в Docker | `docker compose -f infra/docker-compose.dev.yml up --build` |
| Бэкенд-тесты | `cd backend && uv run pytest` (нужен PostgreSQL, переменные `DB_*`) |
| Линтеры бэкенда | `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy .` |
| Безопасность бэкенда | `cd backend && uv run bandit -q -c pyproject.toml -r apps config && uv run pip-audit` |
| Фронтенд dev | `cd frontend && npm run dev` (API проксируется на `VITE_API_PROXY`, по умолчанию `localhost:8000`) |
| Фронтенд проверки | `cd frontend && npm run lint && npm run typecheck && npm test && npm run contrast` |
| Pre-commit | `uv run --project backend pre-commit install`, затем `... pre-commit run --all-files` |

## Правила прав доступа (не нарушать)

1. **Любая проверка прав — на сервере.** Фронтенд только прячет кнопки.
2. **Запрет по умолчанию.** У каждого view — явные `permission_classes`. `AllowAny` — только для URL из `PUBLIC_URL_NAMES` в `apps/core/tests/test_url_permissions.py` (сейчас `health`, на этапе 1 добавится вход). Тест-обходчик падает на любом другом.
3. **Анонимный запрос → 401**, а не 403 (`apps.core.authentication.SessionAuthentication`).
4. **Права на объекты — через queryset:** у каждого менеджера метод `for_user(user)`. Объект вне области видимости — **404**, не 403. Никаких `Model.objects.get(pk=...)` во view без `for_user`.
5. **Сериалайзеры — явный список полей**, никакого `__all__`; отдельные сериалайзеры для ролей. `roles`, `is_active`, `created_by` и подобные поля пишутся только админскими эндпоинтами.
6. **Аудит — в той же транзакции**, что и изменение. Таблица аудита только на добавление (триггер в PostgreSQL), приложение работает под ролью БД без прав суперпользователя.
7. **Средние и проценты считает только сервер** — одной функцией для всех экранов и отчётов.
8. Только ORM; сырой SQL — с параметрами и обоснованием в `docs/decisions.md`.
9. Во фронтенде нет `dangerouslySetInnerHTML` и `innerHTML` (ESLint падает). Пользовательский текст — простой текст.
10. В логах нет паролей, токенов, cookie и телефонов.

## Время и данные

- Метки времени хранятся в UTC, показываются в поясе центра (`Asia/Tashkent`). «Сегодня» считается в поясе центра — на бэкенде через `django.utils.timezone.localdate()`, на фронтенде через `shared/lib/time.ts`.
- Первичные ключи всех сущностей, видимых через API, — UUID.
- PostgreSQL везде, включая тесты. SQLite не используем.

## Дизайн

- «Журнал, а не дэшборд» (SPEC §12). Цвета, шрифты, отступы — только токены из `tokens.css`. Новый цвет — сначала в токены и в `scripts/check-contrast.mjs`.
- Экраны собираются только из компонентов `shared/ui`, которые показаны на `/dev/styleguide`. Новый компонент — сначала в стайлгайд.
- Запрещено: градиенты-украшения, мягкие тени, скругления > 2 px, капс, эмодзи, inline-стили (CSP `style-src 'self'`).
