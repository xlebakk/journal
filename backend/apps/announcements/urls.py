from django.urls import URLPattern, URLResolver, path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False, use_regex_path=False)
router.register(
    "admin/announcements", views.AnnouncementAdminViewSet, basename="admin-announcement"
)

urlpatterns: list[URLPattern | URLResolver] = [
    path("announcements", views.AnnouncementFeedView.as_view(), name="announcements"),
    *router.urls,
]
