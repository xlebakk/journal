from django.urls import URLPattern, URLResolver, path

from . import student_views, views

urlpatterns: list[URLPattern | URLResolver] = [
    path("journal/courses", views.JournalCoursesView.as_view(), name="journal-courses"),
    path("journal/courses/<uuid:pk>", views.JournalGridView.as_view(), name="journal-grid"),
    path("journal/courses/<uuid:pk>/terms", views.JournalTermsView.as_view(), name="journal-terms"),
    path("journal/lessons/<uuid:pk>", views.LessonPageView.as_view(), name="journal-lesson"),
    path(
        "journal/lessons/<uuid:pk>/conduct",
        views.LessonConductView.as_view(),
        name="journal-lesson-conduct",
    ),
    path(
        "journal/lessons/<uuid:pk>/attendance/all-present",
        views.AllPresentView.as_view(),
        name="journal-all-present",
    ),
    path(
        "journal/lessons/<uuid:pk>/attendance/<uuid:student_id>",
        views.AttendanceView.as_view(),
        name="journal-attendance",
    ),
    path(
        "journal/lessons/<uuid:pk>/attendance/<uuid:student_id>/clear",
        views.AttendanceClearView.as_view(),
        name="journal-attendance-clear",
    ),
    path(
        "journal/lessons/<uuid:pk>/grades", views.GradeCreateView.as_view(), name="journal-grades"
    ),
    path("journal/grades/<uuid:pk>", views.GradeView.as_view(), name="journal-grade"),
    path(
        "journal/grades/<uuid:pk>/delete",
        views.GradeDeleteView.as_view(),
        name="journal-grade-delete",
    ),
    path(
        "journal/grades/<uuid:pk>/restore",
        views.GradeRestoreView.as_view(),
        name="journal-grade-restore",
    ),
    path("teacher/today", views.TeacherTodayView.as_view(), name="teacher-today"),
    path("student/home", student_views.StudentHomeView.as_view(), name="student-home"),
    path("student/diary", student_views.StudentDiaryView.as_view(), name="student-diary"),
    path("student/grades", student_views.StudentGradesView.as_view(), name="student-grades"),
    path(
        "student/grades/<uuid:pk>",
        student_views.StudentGradeDetailView.as_view(),
        name="student-grade",
    ),
    path(
        "student/attendance",
        student_views.StudentAttendanceView.as_view(),
        name="student-attendance",
    ),
    path("student/profile", student_views.StudentProfileView.as_view(), name="student-profile"),
]
