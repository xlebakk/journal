from django.urls import URLPattern, URLResolver, path
from rest_framework.routers import SimpleRouter

from apps.audit.views import AuditLogExportView, AuditLogListView, LoginEventListView

from . import views_admin, views_auth, views_import, views_token

router = SimpleRouter(trailing_slash=False, use_regex_path=False)
router.register("admin/users", views_admin.AdminUserViewSet, basename="admin-user")

urlpatterns: list[URLPattern | URLResolver] = [
    path("auth/login", views_auth.LoginView.as_view(), name="auth-login"),
    path("auth/totp", views_auth.TotpLoginView.as_view(), name="auth-totp"),
    path("auth/logout", views_auth.LogoutView.as_view(), name="auth-logout"),
    path("auth/token", views_token.TokenLoginView.as_view(), name="auth-token"),
    path("auth/token/totp", views_token.TokenTotpView.as_view(), name="auth-token-totp"),
    path("auth/token/refresh", views_token.TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("auth/password", views_auth.PasswordChangeView.as_view(), name="auth-password"),
    path("auth/role", views_auth.RoleSwitchView.as_view(), name="auth-role"),
    path("auth/reauth", views_auth.ReauthView.as_view(), name="auth-reauth"),
    path("auth/totp/setup", views_auth.TotpSetupView.as_view(), name="auth-totp-setup"),
    path("auth/totp/backup-codes", views_auth.BackupCodesView.as_view(), name="auth-backup-codes"),
    path("auth/sessions", views_auth.SessionListView.as_view(), name="auth-sessions"),
    path(
        "auth/sessions/end-others",
        views_auth.SessionEndOthersView.as_view(),
        name="auth-sessions-end-others",
    ),
    path("auth/sessions/<uuid:pk>", views_auth.SessionDetailView.as_view(), name="auth-session"),
    path("me", views_auth.MeView.as_view(), name="auth-me"),
    path(
        "admin/users/<uuid:pk>/sessions/<uuid:session_id>",
        views_admin.AdminUserSessionView.as_view(),
        name="admin-user-session",
    ),
    path("admin/audit", AuditLogListView.as_view(), name="admin-audit"),
    path("admin/audit/export", AuditLogExportView.as_view(), name="admin-audit-export"),
    path("admin/login-events", LoginEventListView.as_view(), name="admin-login-events"),
    path(
        "admin/import/students/template",
        views_import.StudentImportTemplateView.as_view(),
        name="admin-import-students-template",
    ),
    path(
        "admin/import/students",
        views_import.StudentImportView.as_view(),
        name="admin-import-students",
    ),
    path(
        "admin/access-cards", views_import.AccessCardInfoView.as_view(), name="admin-access-cards"
    ),
    *router.urls,
]
