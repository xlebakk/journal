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
| 2FA — по желанию пользователя (этап 15); центр может сделать её обязательной для администраторов и для преподавателей, тогда до настройки — 403 `totp_setup_required` | `middleware.totp_setup_required` | `TestTotpSetup` |
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
| `DELETE /auth/totp/setup` | 401 | 204 | 204 (если 2FA не обязательна) | 204 (если 2FA не обязательна), иначе 403 `totp_required` |
| `/admin/users*`, `/admin/audit`, `/admin/login-events` | 401 | 403 | 403 | 200 |
| `GET /schema/` | 401 | 403 | 403 | 200 |
| Администратор в активной роли «преподаватель» → `/admin/*` | — | — | 403 | — |

## Этап 2: структура и расписание

| Мера | Тест |
| --- | --- |
| Все новые `/admin/*` — только активная роль «администратор» | `test_permission_matrix.py` (строки этапа 2) |
| Преподаватель видит только занятия своих курсов, курсов, где он ассистент, и замены; запрос по чужому занятию → 404 | `test_visibility.py::TestTeacherSchedule`, `test_cannot_request_for_someone_elses_lesson` |
| Ученик видит только занятия групп, в которых состоял на дату занятия; после перевода — новой группы | `test_only_own_groups`, `test_transfer_splits_the_schedule_by_date` |
| В ответе ученику нет версий, внутренних id курса и группы и ничего о других учениках | `test_no_internal_or_foreign_data` |
| Пересечения периодов (годы, модули, членство в группе) запрещены на уровне БД | `TestYearsAndTerms`, `test_add_member_and_no_overlapping_periods` |
| Конфликты расписания проверяет сервер при каждом сохранении | `TestSlotConflicts`, `test_move_into_a_conflict_is_blocked` |
| Оптимистичная блокировка: устаревшая `version` → 409 | `test_stale_version_is_409` |
| Изменения структуры, состава групп, шаблона и занятий — в аудите, отмена — с причиной | `test_crud_is_audited`, `test_transfer_closes_old_and_opens_new`, `test_cancel_with_reason_and_version` |
| Некорректные UUID и даты в параметрах → 400, не 500 | `test_list_filters_and_range_limit` |
| Во фронтенде нет inline-стилей (CSP `style-src 'self'`) | ESLint (`no-restricted-syntax`) |

Матрица (этап 2):

| Эндпоинт | Аноним | Ученик | Преподаватель | Администратор |
| --- | --- | --- | --- | --- |
| `/admin/` years, terms, subjects, rooms, work-types, lesson-types, holidays, groups, courses, memberships, slots, lessons, schedule-requests, teachers | 401 | 403 | 403 | 200 |
| `GET /rooms` | 401 | 403 | 200 | 200 |
| `GET /teacher/schedule`, `/teacher/schedule-requests`; `POST /teacher/lessons/{своё}/requests` | 401 | 403 | 200 / 201 | 403 (по активной роли) |
| `POST /teacher/lessons/{чужое}/requests` | 401 | 403 | 404 | 403 |
| `GET /student/schedule` | 401 | 200 (свои группы) | 403 | 403 |

## Этап 3: журнал

| Мера | Тест |
| --- | --- |
| Преподаватель пишет только в занятия своих курсов, где он ассистент, или где он замена; чужой курс → 404 | `test_foreign_course_is_404`, `test_substitute_may_grade_in_his_lesson_only` |
| Ученик не может изменить ни оценку, ни отметку → 403 | `test_student_cannot_touch_the_journal` |
| Оценку правит только её автор (или администратор) | `test_assistant_grades_but_edits_only_own` |
| После окна преподаватель → 403; администратор без причины → 400, с причиной → 200 и запись в аудите | `TestEditWindow` |
| Оценка ученику не из группы на дату занятия или за будущее занятие → 400 | `test_not_in_group_on_that_date`, `test_future_lesson_is_400` |
| Диапазон шкалы — CHECK в БД, лимит оценок — частичный уникальный индекс | `test_value_must_fit_the_year_scale`, `test_at_most_three` |
| Удаление оценки мягкое, остаётся в аудите | `test_soft_delete_and_restore` |
| Оптимистичная блокировка у занятий, отметок и оценок | `test_stale_versions_are_409` |
| Шкала года заперта, если есть оценки; её смена требует повторного ввода пароля | `TestScaleLock` |
| Сетка: число запросов не растёт с числом строк, быстрее 500 мс на 35 × 60 | `test_no_n_plus_one_and_fast` |

Матрица (этап 3):

| Эндпоинт | Аноним | Ученик | Преподаватель | Администратор |
| --- | --- | --- | --- | --- |
| `GET /journal/courses` | 401 | 403 | 200 (свои) | 200 (все) |
| `GET /journal/courses/{свой}`, `/journal/lessons/{своё}` | 401 | 403 | 200 | 200 |
| `GET /journal/courses/{чужой}`, `/journal/lessons/{чужое}` | 401 | 403 | 404 | 200 |
| Запись в журнал в окне | 401 | 403 | 200/201 (свои оценки — только автор) | 200/201 |
| Запись в журнал после окна | 401 | 403 | 403 `edit_window_closed` | 400 без причины, 200 с причиной |
| `GET /teacher/today` | 401 | 403 | 200 | 403 (по активной роли) |

## Этап 4: кабинет ученика

| Мера | Тест |
| --- | --- |
| Все `/student/*` — только активная роль «ученик», сотрудникам 403 | `test_staff_cannot_open_the_student_cabinet`, матрица |
| Ученик A запрашивает оценку ученика B по id → 404; удалённая оценка тоже 404 | `test_someone_elses_grade_is_404`, `test_deleted_grade_is_gone` |
| В дневнике и оценках только свои оценки; служебный комментарий к отметке не показывается | `TestDiary` |
| Профиль ученика без контактов родителей и заметки администратора | `test_profile` |
| Ученик не открывает журнал | e2e `journal.spec.ts` (403) |

## Этап 5: тесты, отчёты, импорт, настройки

| Мера | Тест |
| --- | --- |
| Преподаватель видит только тесты своих курсов и только своих учеников в общем тесте; чужой тест → 404 | `test_foreign_teacher_and_student_do_not_see_exam`, `test_shared_exam_teacher_sees_and_edits_own_groups_only` |
| Результаты: окно как в журнале, после — администратор с причиной; до даты теста — 400 | `TestResults` |
| Итог = сумма разделов, балл в пределах максимума раздела | `test_sections_make_the_total` |
| Ученик видит только свои результаты и свои цели | `test_own_results_with_target_and_change` |
| Объявления по аудитории: группа — только текущим членам; будущие и истёкшие не видны | `TestFeed` |
| Выгрузки — повторный ввод пароля; ячейки-формулы нейтрализованы | `test_export_needs_fresh_password`, `test_formula_injection_is_neutralised`, `test_safe_cell` |
| Импорт: тип по содержимому, лимиты размера и строк, одна транзакция, только без ошибок | `TestStudentImport`, `TestImport` |
| Логотип перекодирован в PNG без метаданных, SVG и GIF отклоняются, лимит 1 МБ | `TestLogo` |
| Изменение настроек — повторный ввод пароля, аудит «было → стало» | `TestSettings` |
| Лимиты: экспорт 20/мин, импорт 10/мин | `throttle_scope` во view (в тестах лимиты выключены) |

Матрица (этап 5):

| Эндпоинт | Аноним | Ученик | Преподаватель | Администратор |
| --- | --- | --- | --- | --- |
| `GET/POST /exams`, `GET /exams/dynamics` | 401 | 403 | 200/201 (свои курсы) | 200/201 |
| `GET/PATCH/DELETE /exams/{id}`, `/results`, `/import`, `/stats` | 401 | 403 | своё — 200, чужое — 404 | 200 |
| `PUT /exams/{id}/results/{student}` после окна | 401 | 403 | 403 `edit_window_closed` | 400 без причины, 200 с причиной |
| `GET /student/exams` | 401 | 200 (свои) | 403 | 403 |
| `GET/PUT /admin/users/{id}/targets` | 401 | 403 | 403 | 200 (не ученик — 404) |
| `GET /announcements` | 401 | 200 (свои) | 200 (свои) | 200 |
| `/admin/announcements` (CRUD) | 401 | 403 | 403 | 200/201/204 |
| `GET /reports/courses/{id}` (`?export=` — с паролем) | 401 | 403 | свой — 200, чужой — 404 | 200 |
| `GET /admin/reports/*`, `/admin/overview`, `/admin/audit/export` | 401 | 403 | 403 | 200 (выгрузка — с паролем) |
| `/admin/import/students`, `/admin/access-cards` | 401 | 403 | 403 | 200 |
| `GET/PATCH /admin/settings`, `POST/DELETE /admin/settings/logo` | 401 | 403 | 403 | 200 (PATCH — с паролем) |

## Этап 6: PWA и Android

| Мера | Тест |
| --- | --- |
| Мобильный вход — те же лимиты, одинаковые ответы и журнал входов, что у сайта; 2FA — одноразовый подписанный билет | `TestLogin` в `test_app_tokens.py` |
| Access-токен 10 минут, подделанный или просроченный → 401 | `test_forged_or_expired_access_is_401` |
| Refresh ротируется; повторное использование старого завершает сеанс | `test_rotation_and_reuse_ends_the_chain` |
| Выход, блокировка, «завершить сеанс», смена пароля действуют на приложение сразу | `TestRevocation` |
| Принудительная смена пароля, повторный ввод пароля и роль в аудите работают с токеном | `TestRulesStillApply` |
| Bearer-запрос игнорирует cookie; CSRF с токеном не нужен | `test_bearer_ignores_the_cookie`, `test_post_needs_no_csrf_with_a_token` |
| CORS только для origin приложения, без credentials | `TestCors` |
| Токены не лежат в `localStorage`; refresh — в Keystore; одно обновление на параллельные 401 | `src/platform/platform.test.ts` |
| Service worker не кэширует API | `npm run check:pwa` (CI) |
| Android: без бэкапа, без cleartext в release, не отлаживаемый, ключ вне репозитория | `mobile/android/app/src/main/AndroidManifest.xml`, `network_security_config.xml`, `build.gradle` |

Публичные эндпоинты (этап 6): `POST /auth/token`, `POST /auth/token/totp`, `POST /auth/token/refresh`. Остальные эндпоинты принимают Bearer-токен наравне с cookie-сессией; права и матрица не меняются.

## Этап 7: продакшен

| Мера | Где проверяется |
| --- | --- |
| Только HTTPS, редирект с HTTP, HSTS год, CSP и заголовки SPEC §11 | `infra/caddy/`, задача CI `prod-stack` |
| Порты наружу публикует только Caddy; PostgreSQL и Redis во внутренней сети без интернета | `docker-compose.prod.yml`, `prod-stack` |
| Контейнеры не от root, корень только для чтения, без capabilities, `no-new-privileges` | `docker-compose.prod.yml`, образы |
| Приложение — роль БД только со строками: не может изменить или удалить журнал аудита, отключить триггер, изменить схему | `db_grants --check` при каждом деплое, `infra/scripts/check-db-roles.sh` (CI) |
| Бэкап зашифрован до записи на диск, хранится вне сервера, 14 / 8 / 12, ежемесячная проверка восстановления | `infra/backup/`, тесты ротации, `prod-stack` |
| Журналы — JSON без паролей, токенов, cookie, телефонов и строк запроса | `apps/core/logging.py`, `test_json_logs_keep_context_and_drop_the_request` |
| Всплески отказов в доступе и входы администраторов с новых устройств — в обзоре | `test_monitoring.py`, `overview.test.tsx` |
| SSH только по ключу, без root, ufw 22/80/443, fail2ban, автообновления безопасности | `infra/server/`, чек-лист в `docs/deploy.md` |

### OWASP ZAP baseline

Скан запускает задача CI `prod-stack` по продакшен-стеку в Docker (`https://localhost`, Caddy, gunicorn, PostgreSQL, Redis). Отчёт сохраняется как артефакт `zap-report`, сводка — в аннотации задачи.

| Дата | Цель | FAIL | WARN | PASS | Комментарий |
| --- | --- | --- | --- | --- | --- |
| 2026-11-22 | `https://localhost`, коммит `1930898` | 0 | 5 | 63 | первый полный прогон |
| 2026-11-22 | `https://localhost`, коммит `75fa360` | 0 | 4 | 64 | после `no-store` для API и COEP |
| 2026-11-22 | `https://journal.localhost`, коммит `c51fa79` | 0 | 3 | 65 | этап 8: первый экран без лишнего кода, «Suspicious Comments» ушло |

Предупреждения первого прогона и что с ними сделано:

| Правило | Что это | Решение |
| --- | --- | --- |
| 10015 Re-examine Cache-control Directives | у ответов API не было `Cache-Control` | **исправлено:** Caddy ставит `Cache-Control: no-store` на `/api/*` (данные детей не попадают в кэш браузера и прокси); CI проверяет заголовок |
| 90004 Cross-Origin-Embedder-Policy Header Missing | нет COEP | **исправлено:** `Cross-Origin-Embedder-Policy: require-corp` — всё грузится с того же источника; e2e проходят с ним |
| 10049 Storable and Cacheable Content | статика кэшируется | так и задумано: хешированные бандлы — `immutable` на год, оболочка — `no-cache` |
| 10027 Information Disclosure — Suspicious Comments | слова вроде «query» в минифицированном JS | ложное срабатывание: в сборке нет комментариев разработчика |
| 10109 Modern Web Application | сайт — одностраничное приложение | информационное |

Оставшееся 10015 — на страницах-оболочке (`/`, маршруты приложения): у них осознанно `no-cache`, а не `no-store` — оболочка не содержит данных, а ревалидация нужна, чтобы обновления доходили сразу. После второго прогона `no-cache` распространён на все ответы, кроме хешированных бандлов (раньше маршруты вроде `/student/diary` отдавали оболочку без `Cache-Control`), и добавлен `robots.txt`, запрещающий индексацию.

## Этап 8: приёмка

| Критерий SPEC §15 | Где проверяется | Результат (2026-11-22, `c51fa79`) |
| --- | --- | --- |
| Mozilla Observatory — A+ | задача CI `prod-stack`, сканер MDN по продакшен-стеку | **A+, 145 баллов** |
| Lighthouse: доступность ≥ 95, производительность ≥ 90 (вход, главная ученика) | `frontend/scripts/lighthouse.mjs`, задача CI `prod-stack`, медиана трёх прогонов | **вход 100 / 100, главная ученика 100 / 100** |
| `check --deploy` без предупреждений | задача CI `backend` | без предупреждений |
| Покрытие `accounts` и `journal` ≥ 85% | задача CI `backend` | 95% |
| Сетка журнала 35 × 60 быстрее 500 мс, без N+1 | `test_no_n_plus_one_and_fast` | проходит |

## Этап 9: отзывы преподавателя

| Мера | Тест |
| --- | --- |
| Пишет только основной преподаватель курса (или администратор); ассистент читает, запись → 403 `not_course_teacher` | `test_assistant_reads_but_does_not_write` |
| Чужой курс → 404, ученик → 403 | `test_foreign_teacher_and_student_get_nothing`, `test_permission_matrix` |
| После окна преподаватель → 403; администратор без причины → 400, с причиной → 200 и причина в аудите | `test_window_teacher_403_admin_with_reason` |
| Отзыв только ученику, бывшему в группе в этом модуле; длина ≤ 600; будущий модуль → 400 | `test_rules` |
| Оптимистичная блокировка; создание, изменение, удаление — в аудите | `test_teacher_writes_updates_and_deletes` |
| Ученик видит только свои отзывы | `test_student_and_parents_see_the_review` |

| Эндпоинт | Аноним | Ученик | Преподаватель | Администратор |
| --- | --- | --- | --- | --- |
| `GET /journal/courses/{свой}/reviews` | 401 | 403 | 200 | 200 |
| `GET /journal/courses/{чужой}/reviews` | 401 | 403 | 404 | 200 |
| `PUT /journal/courses/{свой}/reviews/{ученик}` | 401 | 403 | 200 (основной преподаватель, в окне); ассистент — 403 | 200 (после окна — с причиной) |

## Этап 10: подписка на расписание (iCal)

| Мера | Тест |
| --- | --- |
| Токен — HMAC id ссылки под `SECRET_KEY`, сравнение за постоянное время; в базе секрета нет | `test_token_is_bound_to_the_feed_and_the_key`, `test_old_key_still_opens_links` |
| Неверный токен, перевыпущенная или отключённая ссылка → 404 | `test_wrong_token_reissue_and_revoke` |
| Заблокированный владелец или снятая роль → 404 | `test_link_dies_with_the_account_or_role` |
| В ленте — только занятия, которые владелец видит в своей роли (`for_user`) | `test_student_sees_own_groups_and_cancellations` |
| Ссылка — для активной роли; у администратора её нет | `test_by_active_role`, `test_admin_has_no_feed` |
| Токен не попадает в журналы: он в query-строке, Caddy маскирует `token` | шаг CI «iCal link works and its token stays out of the logs» |
| 60 запросов в час на ссылку | `CalendarFeedThrottle` |

| Эндпоинт | Аноним | Ученик | Преподаватель | Администратор |
| --- | --- | --- | --- | --- |
| `GET /me/calendar` | 401 | 200 | 200 | 403 |
| `POST /me/calendar` (выпуск и перевыпуск) | 401 | 201 | 201 | 403 |
| `DELETE /me/calendar` | 401 | 204 | 204 | 403 |
| `GET /calendar/{id}.ics?token=…` | 200 с верным токеном, иначе 404 | — | — | — |

## Этап 12: оплаты

| Мера | Тест |
| --- | --- |
| Деньги видит и меняет только администратор; преподаватель и ученик → 403 на всех `/admin/payments/*` | `test_teachers_and_students_have_no_admin_access`, `test_permission_matrix` |
| Ученик видит только свой счёт, без аннулированных записей, авторов и причин | `test_student_sees_own_account_without_voided_entries` |
| Карточка «не ученика» → 404 | `test_ledger_of_a_non_student_is_404` |
| Начисление раз в месяц на ученика и группу — уникальность в БД; повтор безопасен | `test_month_charges_members_with_price_minus_discount` |
| Ничего не удаляется: аннулирование с причиной, повторное → 400; всё в аудите | `test_payments_reduce_the_debt_and_voids_restore_it`, `test_voided_charge_is_not_billed_again` |
| Будущий месяц, оплата будущей датой, нулевая сумма, неизвестный способ → 400 | `TestBilling.test_rules`, `TestPayments.test_rules` |
| Суммы — целые, положительные; скидка 1–100 — CHECK в БД | миграция `payments.0001_initial` |

| Эндпоинт | Аноним | Ученик | Преподаватель | Администратор |
| --- | --- | --- | --- | --- |
| `GET /admin/payments/groups`, `PUT /admin/payments/groups/{id}` | 401 | 403 | 403 | 200 / 204 |
| `POST /admin/payments/bill` | 401 | 403 | 403 | 200 |
| `GET /admin/payments/students`, `/students/{ученик}` | 401 | 403 | 403 | 200 (не ученик — 404) |
| `PUT .../discount`, `POST .../payments`, `POST /admin/payments/{charges,payments}/{id}/void` | 401 | 403 | 403 | 204 / 201 / 204 |
| `GET /student/payments` | 401 | 200 (только свой) | 403 | 403 |

## Этап 13: офлайн-режим преподавателя

| Мера | Где проверяется |
| --- | --- |
| Неотправленные изменения — только в памяти вкладки; ни IndexedDB, ни кэша API; service worker по-прежнему не кэширует `/api/` | `offlineQueue.ts`, `check:pwa` |
| Сервер проверяет каждое изменение из очереди как обычное (права, окно, членство, версии); очередь ничего не обходит | серверные тесты журнала |
| Повтор новой оценки не создаёт дубль (`client_key`) | `test_the_same_client_key_creates_one_grade` |
| Отметка без сети ждёт и уходит, когда сеть вернулась | `journal.test.tsx` («offline queue on the grid»), e2e `offline.spec.ts` (`context.setOffline`) |
| Объединение изменений, остановка на сетевой ошибке, конфликты 409 и отказы | `offlineQueue.test.ts` |

## Этап 14: роль «Родитель»

| Мера | Тест |
| --- | --- |
| Родитель видит только привязанных детей: чужой ребёнок → 404, мусор в `child` → 400, без детей → 404 | `test_someone_elses_child_is_404` |
| Всё только чтение: журнал, админка, «Сегодня», календарь → 403; запись оценки → 403 | `test_read_only_and_no_other_sections` |
| Связи создаёт и снимает только администратор; привязать можно только аккаунт с ролью «родитель» и только к ученику | `TestAdminLinks` |
| Объявления — только групп детей, «всем» и «ученикам» | `test_announcements_of_the_childs_groups` |
| Список детей виден только родителю | `test_permission_matrix`, `test_read_only_and_no_other_sections` |

| Эндпоинт | Аноним | Ученик | Родитель | Преподаватель | Администратор |
| --- | --- | --- | --- | --- | --- |
| `GET /student/*?child={свой ребёнок}` | 401 | 200 (свои данные, `child` не влияет) | 200 | 403 | 403 |
| `GET /student/*?child={чужой}` | 401 | 200 (свои) | 404 | 403 | 403 |
| `GET /parent/children` | 401 | 403 | 200 | 403 | 403 |
| `GET, POST /admin/users/{ученик}/parents`, `DELETE .../parents/{родитель}`, `GET /admin/users/{родитель}/children` | 401 | 403 | 403 | 403 | 200 / 201 / 204 |

## Этап 16: суперадмин и разделы администраторов

| Мера | Тест |
| --- | --- |
| Обычный администратор открывает только выданные разделы; «Обзор» — всем администраторам | `test_an_admin_opens_only_the_granted_sections` |
| Любой адрес с `IsAdmin` принадлежит разделу; новый, не внесённый в `ADMIN_PATHS`, доступен только суперадмину | `test_every_admin_route_belongs_to_a_section`, `test_unlisted_admin_paths_are_super_admin_only` |
| Создавать администраторов и выдавать права — только суперадмину (403 `superadmin_required`) | `test_only_the_super_admin_creates_and_grants` |
| Пароль, блокировка, изменения, сеансы администратора — только суперадмину | `test_an_ordinary_admin_cannot_touch_another_admin` |
| Последний суперадмин остаётся | `test_the_last_super_admin_stays` |
| Пароль задаёт администратор; правила сложности — машинными кодами; пароль не попадает ни в ответ, ни в аудит | `test_student_with_generated_login_and_the_admins_password`, `test_the_admin_types_a_good_password` |

## Модель угроз (кратко)

1. **IDOR (подмена ID).** Объекты выбираются только из `for_user()`-queryset; чужое → 404; UUID-ключи. Начиная с этапа 2 каждая новая сущность добавляет строки в матрицу.
2. **Ученик исправляет себе оценку.** У ученика нет изменяющих эндпоинтов, кроме пароля, роли (только своей), 2FA и своих сеансов; оценки и результаты тестов пишут только сотрудники, через сервисы с окном и аудитом.
3. **Подбор пароля преподавателя.** Лимиты по логину и IP, одинаковые ответы, 2FA (может стать обязательной), лимит на коды TOTP.
4. **Украденная сессия.** `HttpOnly` cookie, короткие тайм-ауты у администратора, отзыв сеансов, повторный ввод пароля для опасных действий, смена пароля завершает остальные сеансы. В приложении access-токен живёт 10 минут и только в памяти, refresh — в Keystore, ротируется, а повторное использование завершает сеанс; сеанс телефона виден в списке сеансов и отзывается оттуда.
8. **Потерянный телефон.** Резервные копии данных приложения запрещены; вход завершается из «Активных сеансов» на сайте или администратором (блокировка, сброс пароля).
5. **Утечка данных несовершеннолетних.** Минимум полей; контакты родителей — только администратору; в логах нет паролей, токенов и телефонов; выгрузки — с повторным вводом пароля и лимитом.
7. **Вредоносный файл.** Импорт читает XLSX без формул и с `defusedxml`, тип — по содержимому, лимиты размера и строк; экспорт нейтрализует формулы; логотип перекодируется, его файл не отдаётся по URL.
6. **Подделка аудита.** Триггер запрещает UPDATE и DELETE, а в продакшене у роли приложения нет ни прав UPDATE/DELETE/TRUNCATE на журнал аудита, ни владения таблицами — отключить триггер она не может. Миграции идут под отдельной ролью-владельцем.
9. **Потеря сервера или данных.** Еженочный зашифрованный бэкап вне сервера, ежемесячная автоматическая проверка восстановления; ключ расшифровки и `.env.prod` хранятся у владельца вне сервера.
10. **Перебор чужих записей.** Объекты вне области видимости дают 404; каждый такой отказ записывается, и всплеск виден администратору в обзоре.
