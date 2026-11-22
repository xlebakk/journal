from django.urls import URLPattern, URLResolver, path

from . import views

urlpatterns: list[URLPattern | URLResolver] = [
    path("admin/payments/groups", views.GroupFeesView.as_view(), name="admin-payment-groups"),
    path(
        "admin/payments/groups/<uuid:pk>", views.GroupFeeView.as_view(), name="admin-payment-group"
    ),
    path("admin/payments/bill", views.BillView.as_view(), name="admin-payment-bill"),
    path("admin/payments/students", views.StudentListView.as_view(), name="admin-payment-students"),
    path(
        "admin/payments/students/<uuid:pk>",
        views.StudentLedgerView.as_view(),
        name="admin-payment-student",
    ),
    path(
        "admin/payments/students/<uuid:pk>/discount",
        views.StudentDiscountView.as_view(),
        name="admin-payment-discount",
    ),
    path(
        "admin/payments/students/<uuid:pk>/payments",
        views.StudentPaymentsView.as_view(),
        name="admin-payment-create",
    ),
    path(
        "admin/payments/charges/<uuid:pk>/void",
        views.VoidChargeView.as_view(),
        name="admin-charge-void",
    ),
    path(
        "admin/payments/payments/<uuid:pk>/void",
        views.VoidPaymentView.as_view(),
        name="admin-payment-void",
    ),
    path("student/payments", views.MyPaymentsView.as_view(), name="student-payments"),
]
