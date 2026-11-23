from django.urls import path

from . import views, views_settings

urlpatterns = [
    path("health", views.HealthView.as_view(), name="health"),
    path("admin/settings", views_settings.CenterSettingsView.as_view(), name="admin-settings"),
    path("admin/settings/logo", views_settings.LogoView.as_view(), name="admin-settings-logo"),
    path(
        "admin/settings/video",
        views_settings.LoginVideoView.as_view(),
        name="admin-settings-video",
    ),
    path(
        "branding/video/<str:name>",
        views_settings.LoginVideoFileView.as_view(),
        name="branding-video",
    ),
]
