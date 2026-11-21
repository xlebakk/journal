# Безопасность

Цель — OWASP ASVS уровня 2 (SPEC §11). Документ растёт вместе с этапами. Каждая строка матрицы прав — параметризованный тест в `backend/apps/accounts/tests/test_permission_matrix.py`.

## Что действует (этапы 0–1)

### Аутентификация

| Мера | Где | Тест |
| --- | --- | --- |
| Одна форма входа; ответ «неверный логин или пароль» одинаков для неверного пароля, несуществующего и отключённого логина — байт в байт | `views_auth.LoginView` | `test_login.py::test_wrong_password_and_unknown_login_look_identical` |
| Для несуществующего логина выполняется проверка хэша-пустышки Argon2 (одинаковое время) | `_DUMMY_HASH` | `test_unknown_login_still_checks_a_password_hash` |
| 5 неудач → блокировка 15 мин, повтор ×2 до 24 ч; 6-я попытка → 429, одинаково и для несуществующих логинов | `lockout.py` | `TestLockout` |
| По IP — 20 попыток за 10 минут | `lockout.ip_over_limit_seconds` | `test_ip_limit` |
| CSRF на входе и шаге TOTP (не только для залогиненных) | `core/csrf.py` | `TestCsrfAndCookies` |
| Argon2id, длина ≥ 10, список распространённых, непохожесть на логин и ФИО; фразы без спецсимволов допустимы | `AUTH_PASSWORD_VALIDATORS` | `TestTemporaryPassword` |
| Временный пароль: до смены любой запрос, кроме `/me`, `/auth/password`, `/auth/logout`, → 403 `password_change_required` | `ForcedActionMiddleware` | `test_only_password_change_is_allowed` |
| Администратору 2FA обязательна; до настройки — 403 `totp_setup_required`; администратор может сделать 2FA обязательной для преподавателей | `middleware.totp_setup_required` | `TestTotpSetup` |
| TOTP-секрет зашифрован (Fernet, ключи из окружения, ротация через MultiFernet); код нельзя использовать повторно; 5 неверных кодов → вход заново + засчитанная неудача | `totp.py` | `TestTotpLogin` |
| 10 резервных кодов, одноразовые, хранятся как HMAC | `totp.generate_backup_codes` | `test_backup_code_works_once` |
| Cookie `__Host-session`: `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`, без `Domain` | `settings/base.py` | `test_session_cookie_flags` |
| Новый id сессии при входе, смене пароля и смене роли | `sessions.start_session`, `cycle_session_key` | `test_session_id_changes_on_login`, `TestRoleSwitch` |
| Тайм-ауты по самой строгой роли аккаунта: администратор 30 мин / 8 ч; преподаватель 2 ч / 12 ч (14 дней с «Запомнить»); ученик 12 ч (30 дней) | `sessions.policy_for` | `TestSessionPolicy` |
| Смена пароля завершает остальные сеансы; сброс пароля, блокировка, архив, смена ролей и сброс 2FA — все сеансы пользователя | `sessions.end_user_sessions` | `test_change_ends_other_sessions_and_is_audited`, `TestAccountActions` |
| Список своих сеансов, завершение одного и всех, кроме текущего; чужой сеанс → 404 | `/auth/sessions` | `TestOwnSessions` |
| Повторный ввод пароля (5 мин) для опасных действий; неверный пароль засчитывается в блокировку | `permissions.require_recent_password` | `TestReauth`, `test_roles_change_needs_fresh_password_and_ends_sessions` |

### Авторизация

| Мера | Тест |
| --- | --- |
| Запрет по умолчанию; у каждого view явные права; `AllowAny` только у `health`, `auth-login`, `auth-totp` | `core/tests/test_url_permissions.py` (обходит все URL) |
| Анонимный запрос к любому другому `/api/` → 401 | тот же обходчик, для каждого метода |
| Права по *активной* роли сессии; роль должна быть в ролях пользователя | `test_admin_in_teacher_role_has_no_admin_access` |
| Объект вне области видимости → 404 (`for_user()`, `get_object_or_404` по своему queryset) | `test_cannot_revoke_someone_elses_session`, `test_session_of_another_user_is_404`, `test_unknown_id_is_404` |
| Сериалайзеры с явными полями; `roles`, `is_active` и т. п. меняются только админскими эндпоинтами | `test_privileged_fields_cannot_be_set_through_self_service` |
| Ученик ни с какой ролью не совмещается — CHECK в БД и валидация API | `test_invalid_roles` |
| Нельзя заблокировать, архивировать себя или лишить себя роли admin; нельзя убрать последнего активного администратора | `TestUpdate`, `TestAccountActions` |
| OpenAPI-схема — только администратору | матрица: `GET /api/v1/schema/` |

### Данные и аудит

| Мера | Тест |
| --- | --- |
| Журнал аудита только на добавление: триггер PostgreSQL отклоняет UPDATE и DELETE (и через ORM, и сырым SQL) | `audit/tests/test_audit.py::TestAppendOnly` |
| Запись аудита возможна только внутри транзакции изменения | `test_record_requires_a_transaction` |
| Пароли, TOTP-секреты, хэши кодов и ключей сессий не попадают в аудит, журнал входов и логи | `test_secrets_never_reach_the_log`, `test_events_are_logged_without_password` |
| Контакты родителей и заметка администратора — только в админских сериалайзерах | `test_detail_shows_parent_contacts_to_admin`; `/me` таких полей не содержит |

### HTTP, инфраструктура, зависимости

Без изменений с этапа 0: HSTS, редирект на HTTPS, `nosniff`, `Referrer-Policy`, COOP, `X-Frame-Options: DENY`, `check --deploy` в CI. Нет inline-скриптов, `innerHTML` и `dangerouslySetInnerHTML`. Контейнер API запускается не от root. Redis закрыт паролем. В CI — `pip-audit`, `npm audit`, `bandit`, Dependabot.

## Матрица прав (этап 1)

| Эндпоинт | Аноним | Ученик | Преподаватель | Администратор |
| --- | --- | --- | --- | --- |
| `GET /health` | 200 | 200 | 200 | 200 |
| `GET, POST /auth/login`, `POST /auth/totp` | 200 / 400 / 429 | — | — | — |
| `GET /me`, `POST /auth/logout`, `/auth/password`, `/auth/role`, `/auth/reauth` | 401 | 200 | 200 | 200 |
| `GET /auth/sessions`, `DELETE /auth/sessions/{свой}` | 401 | 200 / 204 | 200 / 204 | 200 / 204 |
| `DELETE /auth/sessions/{чужой}` | 401 | 404 | 404 | 404 |
| `/auth/totp/setup` (GET/POST), `/auth/totp/backup-codes` | 401 | 200 | 200 | 200 |
| `DELETE /auth/totp/setup` | 401 | 204 | 204 (если 2FA не обязательна) | 403 `totp_required` |
| `/admin/users*`, `/admin/audit`, `/admin/login-events` | 401 | 403 | 403 | 200 |
| `GET /schema/` | 401 | 403 | 403 | 200 |
| Администратор в активной роли «преподаватель» → `/admin/*` | — | — | 403 | — |

## Модель угроз (кратко)

1. **IDOR (подмена ID).** Объекты выбираются только из `for_user()`-queryset; чужое → 404; UUID-ключи. Начиная с этапа 2 каждая новая сущность добавляет строки в матрицу.
2. **Ученик исправляет себе оценку.** У ученика нет изменяющих эндпоинтов, кроме пароля, роли (только своей), 2FA и своих сеансов. Оценки — этап 3.
3. **Подбор пароля преподавателя.** Лимиты по логину и IP, одинаковые ответы, 2FA (может стать обязательной), лимит на коды TOTP.
4. **Украденная сессия.** `HttpOnly` cookie, короткие тайм-ауты у администратора, отзыв сеансов, повторный ввод пароля для опасных действий, смена пароля завершает остальные сеансы.
5. **Утечка данных несовершеннолетних.** Минимум полей; контакты родителей — только администратору; в логах нет паролей, токенов и телефонов.
6. **Подделка аудита.** Триггер запрещает UPDATE и DELETE. **Ограничение до этапа 7:** приложение пока работает под ролью-владельцем таблиц, которая может отключить триггер; разделение ролей БД — в продакшен-этапе (`docs/decisions.md`).
