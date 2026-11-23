from django.urls import URLPattern, URLResolver, path
from rest_framework.routers import SimpleRouter

from apps.academics import views as academics

from . import calendar_views, views

router = SimpleRouter(trailing_slash=False, use_regex_path=False)
router.register("admin/years", academics.AcademicYearViewSet, basename="admin-year")
router.register("admin/terms", academics.TermViewSet, basename="admin-term")
router.register("admin/subjects", academics.SubjectViewSet, basename="admin-subject")
router.register("admin/rooms", academics.RoomViewSet, basename="admin-room")
router.register("admin/work-types", academics.WorkTypeViewSet, basename="admin-work-type")
router.register("admin/lesson-types", academics.LessonTypeViewSet, basename="admin-lesson-type")
router.register("admin/holidays", academics.HolidayViewSet, basename="admin-holiday")
router.register("admin/groups", academics.GroupViewSet, basename="admin-group")
router.register("admin/courses", academics.CourseViewSet, basename="admin-course")
router.register("admin/slots", views.AdminSlotViewSet, basename="admin-slot")
router.register("admin/lessons", views.AdminLessonViewSet, basename="admin-lesson")
router.register(
    "admin/schedule-requests", views.AdminScheduleRequestViewSet, basename="admin-schedule-request"
)

urlpatterns: list[URLPattern | URLResolver] = [
    path(
        "admin/memberships/<uuid:pk>", academics.MembershipView.as_view(), name="admin-membership"
    ),
    path(
        "admin/memberships/<uuid:pk>/leave",
        academics.MembershipLeaveView.as_view(),
        name="admin-membership-leave",
    ),
    path(
        "admin/memberships/<uuid:pk>/transfer",
        academics.MembershipTransferView.as_view(),
        name="admin-membership-transfer",
    ),
    path("admin/teachers", academics.TeacherOptionsView.as_view(), name="admin-teachers"),
    path("rooms", views.RoomOptionsView.as_view(), name="rooms"),
    path("admin/availability", views.AvailabilityView.as_view(), name="admin-availability"),
    path("me/calendar", calendar_views.MyCalendarView.as_view(), name="me-calendar"),
    path("calendar/<uuid:pk>.ics", calendar_views.CalendarFeedView.as_view(), name="calendar-feed"),
    path("teacher/schedule", views.TeacherScheduleView.as_view(), name="teacher-schedule"),
    path(
        "teacher/lessons/<uuid:pk>/requests",
        views.TeacherLessonRequestView.as_view(),
        name="teacher-lesson-request",
    ),
    path(
        "teacher/schedule-requests",
        views.TeacherRequestListView.as_view(),
        name="teacher-schedule-requests",
    ),
    path(
        "teacher/schedule-requests/<uuid:pk>/withdraw",
        views.TeacherRequestWithdrawView.as_view(),
        name="teacher-schedule-request-withdraw",
    ),
    path("student/schedule", views.StudentScheduleView.as_view(), name="student-schedule"),
    *router.urls,
]
