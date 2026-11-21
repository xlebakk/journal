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
  apps/core/        общее: health, SessionAuthentication с 401, обработчики 404/500,
                    files.py (чтение XLSX/CSV, выгрузки с защитой от формул), настройки и логотип
  apps/accounts/    пользователи, профили, вход, 2FA (totp.py), блокировки (lockout.py),
                    сеансы и тайм-ауты (sessions.py, middleware.py), права (permissions.py)
  apps/audit/       AuditLog (только INSERT, триггер) и services.record()
  apps/academics/   годы, модули, предметы, кабинеты, виды занятий и работ, нерабочие дни,
                    группы и составы (exclusion-ограничения), курсы с ассистентами
  apps/schedule/    шаблон недели (ScheduleSlot), занятия (Lesson, planned_* для переносов),
                    запросы преподавателей; вся логика — services.py (генерация, конфликты, план)
  apps/journal/     посещаемость и оценки; правила — services.py, формулы — stats.py (одна функция)
  apps/exams/       пробные тесты, разделы, результаты, цели учеников; правила — services.py
  apps/announcements/ объявления: для всех, роли или групп (for_user, live)
  apps/reports/     отчёты и выгрузки (?export=xlsx|csv), обзор администратора
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
| Демо-данные | `uv run python manage.py seed_demo` (только DEBUG, пустая база) |
| e2e | `cd frontend && npm run e2e` (база `journal_e2e`, пересоздаётся каждый прогон) |
| OpenAPI → типы | `manage.py spectacular --settings=config.settings.test --file ../frontend/src/shared/api/schema.yml`, затем `npm run api:types` |
| Линтеры бэкенда | `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy .` |
| Безопасность бэкенда | `cd backend && uv run bandit -q -c pyproject.toml -r apps config && uv run pip-audit` |
| Фронтенд dev | `cd frontend && npm run dev` (API проксируется на `VITE_API_PROXY`, по умолчанию `localhost:8000`) |
| Фронтенд проверки | `cd frontend && npm run lint && npm run typecheck && npm test && npm run contrast` |
| Pre-commit | `uv run --project backend pre-commit install`, затем `... pre-commit run --all-files` |

## Правила прав доступа (не нарушать)

1. **Любая проверка прав — на сервере.** Фронтенд только прячет кнопки.
2. **Запрет по умолчанию.** У каждого view — явные `permission_classes`. `AllowAny` — только для URL из `PUBLIC_URL_NAMES` в `apps/core/tests/test_url_permissions.py` (`health`, `auth-login`, `auth-totp`). Тест-обходчик падает на любом другом.
   Роль проверяется по **активной** роли сессии: `IsAdmin`, `IsTeacher`, `IsStudent` из `apps/accounts/permissions.py`. Текущий пользователь во view — `current_user(request)`.
   Опасные действия (роли, 2FA, позже — шкала, экспорт ПД) вызывают `require_recent_password(request)`.
3. **Анонимный запрос → 401**, а не 403 (`apps.core.authentication.SessionAuthentication`).
4. **Права на объекты — через queryset:** у каждого менеджера метод `for_user(user)`. Объект вне области видимости — **404**, не 403. Никаких `Model.objects.get(pk=...)` во view без `for_user`.
5. **Сериалайзеры — явный список полей**, никакого `__all__`; отдельные сериалайзеры для ролей. `roles`, `is_active`, `created_by` и подобные поля пишутся только админскими эндпоинтами.
6. **Аудит — в той же транзакции**, что и изменение: `with transaction.atomic(): ...; audit.record(request=..., action="entity.verb", entity=obj, before=..., after=...)`. `record()` падает вне транзакции. Секретные поля (`SECRET_FIELDS`) отрезаются автоматически. Таблица аудита только на добавление (триггер в PostgreSQL), приложение работает под ролью БД без прав суперпользователя.
7. **Ошибки API — машинные коды** `{"detail": "<code>"}` / `{"поле": ["<code>"]}`; перевод — в `frontend/src/shared/i18n/ru.json` (`errors.*`). Новый код — сразу и перевод.
8. **Средние и проценты считает только сервер** — одной функцией для всех экранов и отчётов.
9. Только ORM; сырой SQL — с параметрами и обоснованием в `docs/decisions.md`.
10. Во фронтенде нет `dangerouslySetInnerHTML` и `innerHTML` (ESLint падает). Пользовательский текст — простой текст.
11. В логах нет паролей, токенов, cookie и телефонов.
12. Матрица прав в `docs/security.md` и `apps/accounts/tests/test_permission_matrix.py` растёт с каждым новым эндпоинтом.
13. Админский CRUD — `apps.core.viewsets.AuditedAdminViewSet`: аудит, 409 `in_use`, коды нарушений ограничений через `constraint_codes`. Сериалайзеры моделей — `apps.core.serializers.DatabaseUniqueModelSerializer`: уникальность проверяет БД.
14. Query-параметры с id и датами — через `apps.core.params.uuid_param` / `date_param` (мусор → 400).
15. Занятия по ролям — `Lesson.objects.for_user(user, role)` с **активной** ролью; изменение занятия — под `services.lock_lesson(id, version)` (оптимистичная блокировка).
16. Любая запись в журнал — только через `apps/journal/services.py` (окно, причина, членство, автор оценки, версии, аудит). Средние и проценты — только `apps/journal/stats.py:course_stats` (по курсу — `summarise_group`); новый экран или отчёт с цифрами вызывает их же.
17. Выгрузка файла (`?export=xlsx|csv`) — экспорт ПД: `require_recent_password` и `throttle_scope = "export"`; файлы — только через `apps/core/files.py` (`read_table`, `export`). Результаты тестов — только через `apps/exams/services.py`.

## Время и данные

- Метки времени хранятся в UTC, показываются в поясе центра (`Asia/Tashkent`). «Сегодня» считается в поясе центра — на бэкенде через `django.utils.timezone.localdate()`, на фронтенде через `shared/lib/week.ts: centerToday()`. В расписании «сегодня» — `apps.schedule.services.today()`, его подменяют тесты.
- Дата и время занятия — гражданские (`DateField` + `TimeField`) в поясе центра, не UTC.
- Первичные ключи всех сущностей, видимых через API, — UUID.
- PostgreSQL везде, включая тесты. SQLite не используем.

## Дизайн

- «Журнал, а не дэшборд» (SPEC §12). Цвета, шрифты, отступы — только токены из `tokens.css`. Новый цвет — сначала в токены и в `scripts/check-contrast.mjs`.
- Экраны собираются только из компонентов `shared/ui`, которые показаны на `/dev/styleguide`. Новый компонент — сначала в стайлгайд.
- Запрещено: градиенты-украшения, мягкие тени, скругления > 2 px, капс, эмодзи, inline-стили (CSP `style-src 'self'`; атрибут `style` запрещён в ESLint).
- Даты занятий во фронтенде — ISO-строки гражданской даты (`shared/lib/week.ts`), без пересчёта через пояс браузера.
