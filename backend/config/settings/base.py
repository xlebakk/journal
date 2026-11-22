"""Settings shared by all environments. Environment-specific files import * from here."""

from pathlib import Path

from config.env import env_int, env_list, env_str

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = env_str("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.postgres",
    "rest_framework",
    "drf_spectacular",
    "apps.core",
    "apps.accounts",
    "apps.audit",
    "apps.academics",
    "apps.schedule",
    "apps.journal",
    "apps.exams",
    "apps.announcements",
    "apps.reports",
    "apps.payments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # CORS for the Android app only (no cookies): before anything that may answer.
    "apps.core.cors.AppCorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Timeouts by role, revoked sessions, forced password change / 2FA setup.
    "apps.accounts.middleware.SessionPolicyMiddleware",
    "apps.accounts.middleware.AppTokenMiddleware",
    "apps.accounts.middleware.ForcedActionMiddleware",
    # Refused requests of logged-in users, for «всплески отказов» in the overview.
    "apps.audit.middleware.DeniedRequestMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    }
]

# --- Database: PostgreSQL everywhere, no SQLite (constraints and triggers must match prod).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_str("DB_NAME", "journal"),
        "USER": env_str("DB_USER", "journal"),
        "PASSWORD": env_str("DB_PASSWORD"),
        "HOST": env_str("DB_HOST", "localhost"),
        "PORT": env_int("DB_PORT", 5432),
        "ATOMIC_REQUESTS": False,
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"connect_timeout": 5},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Cache and sessions: Redis.
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env_str("REDIS_URL", "redis://localhost:6379/0"),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
# Upper bound only; the real per-role limits live in CenterSettings (apps.accounts.sessions).
SESSION_COOKIE_AGE = 30 * 24 * 3600

# --- 2FA. Fernet keys, comma-separated; the first one encrypts, all decrypt (rotation).
TOTP_ENCRYPTION_KEYS = env_list("TOTP_ENCRYPTION_KEYS")
TOTP_ISSUER = env_str("TOTP_ISSUER", "Journal")

# Number of reverse proxies in front of Django whose X-Forwarded-For can be trusted.
TRUSTED_PROXY_COUNT = env_int("TRUSTED_PROXY_COUNT", 0)

# Login limits per IP (SPEC §11): attempts per window.
LOGIN_IP_LIMIT = 20
LOGIN_IP_WINDOW_SECONDS = 600
TOTP_MAX_ATTEMPTS = 5
REAUTH_VALID_SECONDS = 300

# --- Users and passwords.
AUTH_USER_MODEL = "accounts.User"
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {"user_attributes": ("login", "last_name", "first_name", "middle_name")},
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

# --- Localisation. Timestamps are stored in UTC; TIME_ZONE is the center's zone for display.
LANGUAGE_CODE = "ru"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Uploaded files live outside the web root and are served only through the API (SPEC §11).
MEDIA_ROOT = Path(env_str("MEDIA_ROOT", str(BASE_DIR / "media")))
LOGO_MAX_BYTES = 1024 * 1024

# Android app (SPEC §11, stage 6): access token in memory, refresh token in the Keystore.
APP_ACCESS_SECONDS = 600
APP_REFRESH_DAYS = 30
# Origins of the Capacitor WebView (androidScheme https; iOS later uses capacitor://).
APP_ORIGINS = env_list("APP_ORIGINS", ["https://localhost", "capacitor://localhost"])
IMPORT_MAX_BYTES = 5 * 1024 * 1024

# --- Cookies. Same origin as the frontend, so no CORS.
SESSION_COOKIE_NAME = "__Host-session"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_PATH = "/"
CSRF_COOKIE_NAME = "__Host-csrftoken"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# --- API. Deny by default: every view must declare its permission classes explicitly.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.core.authentication.AppTokenAuthentication",
        "apps.core.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
        # Applies only to views with `throttle_scope` (exports, imports).
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    # Exports and imports are stricter than the general limit (SPEC §11).
    "DEFAULT_THROTTLE_RATES": {
        "user": "300/min",
        "anon": "60/min",
        "export": "20/min",
        "import": "10/min",
        "calendar": "60/hour",
    },
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.Pagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "apps.core.exceptions.exception_handler",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Journal API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["apps.accounts.permissions.IsAdmin"],
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "RoleEnum": "apps.accounts.models.Role",
        "LessonStatusEnum": "apps.schedule.models.LessonStatus",
        "ScheduleRequestStatusEnum": "apps.schedule.models.ScheduleRequest.Status",
        "ScheduleRequestKindEnum": "apps.schedule.models.ScheduleRequest.Kind",
        "GradeScaleEnum": "apps.academics.models.GradeScale",
        "WeekdayEnum": "apps.schedule.models.Weekday",
        "AttendanceStatusEnum": "apps.journal.models.AttendanceStatus",
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
