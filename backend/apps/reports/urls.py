from django.urls import URLPattern, URLResolver, path

from . import overview, views

urlpatterns: list[URLPattern | URLResolver] = [
    path("admin/overview", overview.OverviewView.as_view(), name="admin-overview"),
    path("reports/courses/<uuid:pk>", views.CourseStatementView.as_view(), name="report-course"),
    path(
        "admin/reports/performance",
        views.PerformanceReportView.as_view(),
        name="admin-report-performance",
    ),
    path(
        "admin/reports/fill-rate", views.FillRateReportView.as_view(), name="admin-report-fill-rate"
    ),
    path(
        "admin/reports/students/<uuid:pk>",
        views.StudentSummaryView.as_view(),
        name="admin-report-student",
    ),
]
