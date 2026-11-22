from django.urls import URLPattern, URLResolver, include, path
from drf_spectacular.views import SpectacularAPIView

api_v1: list[URLPattern | URLResolver] = [
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.schedule.urls")),
    path("", include("apps.journal.urls")),
    path("", include("apps.exams.urls")),
    path("", include("apps.announcements.urls")),
    path("", include("apps.reports.urls")),
    path("", include("apps.payments.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
]

urlpatterns = [
    path("api/v1/", include(api_v1)),
]

handler404 = "apps.core.views.not_found"
handler500 = "apps.core.views.server_error"
