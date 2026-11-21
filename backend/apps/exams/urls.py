from django.urls import URLPattern, URLResolver, path

from . import views

urlpatterns: list[URLPattern | URLResolver] = [
    path("exams", views.ExamListView.as_view(), name="exams"),
    path("exams/dynamics", views.ExamDynamicsView.as_view(), name="exams-dynamics"),
    path("exams/<uuid:pk>", views.ExamDetailView.as_view(), name="exam"),
    path("exams/<uuid:pk>/results", views.ExamResultsView.as_view(), name="exam-results"),
    path(
        "exams/<uuid:pk>/results/<uuid:student_id>",
        views.ExamResultView.as_view(),
        name="exam-result",
    ),
    path(
        "exams/<uuid:pk>/results/<uuid:student_id>/clear",
        views.ExamResultClearView.as_view(),
        name="exam-result-clear",
    ),
    path("exams/<uuid:pk>/import", views.ExamImportView.as_view(), name="exam-import"),
    path("exams/<uuid:pk>/stats", views.ExamStatsView.as_view(), name="exam-stats"),
    path("student/exams", views.StudentExamsView.as_view(), name="student-exams"),
    path(
        "admin/users/<uuid:pk>/targets",
        views.StudentTargetsView.as_view(),
        name="admin-user-targets",
    ),
]
