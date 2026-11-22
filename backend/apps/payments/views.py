"""Payments: the administrator bills, takes payments and voids mistakes; a student sees their
own account. Teachers have nothing here (the user's answer before stage 12)."""

from typing import Any

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import AcademicYear, Group, GroupMembership
from apps.accounts.models import Role, User
from apps.accounts.permissions import STUDENT_PAGES, IsAdmin, subject_student
from apps.core.params import uuid_param

from . import serializers as s
from . import services
from .models import Charge, Payment, StudentDiscount


def _students() -> Any:
    return User.objects.with_role(Role.STUDENT)


def _entries(student: User, *, admin: bool) -> list[dict[str, Any]]:
    charges = Charge.objects.filter(student=student).select_related("group", "created_by")
    payments = Payment.objects.filter(student=student).select_related("created_by")
    if not admin:
        charges = charges.filter(voided_at__isnull=True)
        payments = payments.filter(voided_at__isnull=True)
    rows: list[dict[str, Any]] = [
        {
            "kind": "charge",
            "id": c.pk,
            "date": c.month,
            "amount": c.amount,
            "group_name": c.group.name,
            "full_amount": c.full_amount,
            "discount_percent": c.discount_percent,
            "method": "",
            "comment": "",
            "voided": c.voided_at is not None,
            "void_reason": c.void_reason,
            "author_name": c.created_by.short_name if c.created_by else "",
        }
        for c in charges
    ]
    rows += [
        {
            "kind": "payment",
            "id": p.pk,
            "date": p.paid_on,
            "amount": p.amount,
            "group_name": "",
            "full_amount": None,
            "discount_percent": None,
            "method": p.method,
            "comment": p.comment,
            "voided": p.voided_at is not None,
            "void_reason": p.void_reason,
            "author_name": p.created_by.short_name,
        }
        for p in payments
    ]
    # Newest first; on the same day a payment goes above the charge.
    rows.sort(key=lambda r: (r["date"], r["kind"] == "payment"), reverse=True)
    return rows


def _ledger(student: User, *, admin: bool) -> dict[str, Any]:
    total = services.balance(student)
    return {
        "student": student.pk,
        "full_name": student.full_name,
        "login": student.login,
        "charged": total.charged,
        "paid": total.paid,
        "debt": total.debt,
        "discount_percent": services.discount_of(student),
        "entries": _entries(student, admin=admin),
    }


class GroupFeesView(APIView):
    """Prices of the current year's groups (and of any group that still has one)."""

    permission_classes = (IsAdmin,)

    @extend_schema(responses=s.GroupFeesSerializer)
    def get(self, request: Request) -> Response:
        day = timezone.localdate()
        year = AcademicYear.objects.filter(is_current=True).first()
        groups = (
            Group.objects.filter(Q(academic_year=year) | Q(fee__isnull=False))
            .select_related("academic_year", "fee")
            .annotate(
                members_count=Count(
                    "memberships",
                    filter=Q(memberships__joined_on__lte=day)
                    & (Q(memberships__left_on__isnull=True) | Q(memberships__left_on__gte=day)),
                    distinct=True,
                )
            )
            .order_by("is_archived", "name")
        )
        month = services.month_start(day)
        data = {
            "month": month,
            "month_charges": Charge.objects.filter(month=month).count(),
            "groups": [
                {
                    "id": g.pk,
                    "name": g.name,
                    "year_name": g.academic_year.name,
                    "is_archived": g.is_archived,
                    "members_count": getattr(g, "members_count", 0),
                    "monthly_amount": g.fee.monthly_amount if hasattr(g, "fee") else 0,
                }
                for g in groups
            ],
        }
        return Response(s.GroupFeesSerializer(data).data)


class GroupFeeView(APIView):
    permission_classes = (IsAdmin,)

    @extend_schema(request=s.GroupFeeWriteSerializer, responses={204: None})
    def put(self, request: Request, pk: str) -> Response:
        group = get_object_or_404(Group, pk=pk)
        form = s.GroupFeeWriteSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        services.set_group_fee(request, group, form.validated_data["monthly_amount"])
        return Response(status=204)


class BillView(APIView):
    """«Начислить за месяц»: safe to press twice."""

    permission_classes = (IsAdmin,)

    @extend_schema(request=s.BillWriteSerializer, responses=s.BillResultSerializer)
    def post(self, request: Request) -> Response:
        form = s.BillWriteSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        result = services.bill_month(request, form.validated_data["month"])
        return Response(s.BillResultSerializer(result).data)


class StudentListView(APIView):
    permission_classes = (IsAdmin,)

    @extend_schema(
        operation_id="admin_payments_students_list",
        parameters=[
            OpenApiParameter("group", str),
            OpenApiParameter("q", str),
            OpenApiParameter("debtors", bool),
        ],
        responses=s.StudentListSerializer,
    )
    def get(self, request: Request) -> Response:
        students = _students().order_by("last_name", "first_name")
        group = uuid_param(request, "group")
        if group:
            students = students.filter(memberships__group_id=group).distinct()
        query = (request.query_params.get("q") or "").strip()
        if query:
            students = students.filter(
                Q(last_name__icontains=query)
                | Q(first_name__icontains=query)
                | Q(login__icontains=query)
            )
        people = list(students)
        totals = services.balances([p.pk for p in people])
        discounts = dict(
            StudentDiscount.objects.filter(student__in=people).values_list("student_id", "percent")
        )
        day = timezone.localdate()
        groups: dict[Any, list[str]] = {}
        for student_id, name in (
            GroupMembership.objects.filter(student__in=people, joined_on__lte=day)
            .filter(Q(left_on__isnull=True) | Q(left_on__gte=day))
            .order_by("group__name")
            .values_list("student_id", "group__name")
        ):
            groups.setdefault(student_id, []).append(name)
        rows = [
            {
                "id": p.pk,
                "full_name": p.full_name,
                "login": p.login,
                "groups": groups.get(p.pk, []),
                "discount_percent": discounts.get(p.pk, 0),
                "charged": totals[p.pk].charged,
                "paid": totals[p.pk].paid,
                "debt": totals[p.pk].debt,
            }
            for p in people
        ]
        debtors = [r for r in rows if r["debt"] > 0]
        if request.query_params.get("debtors") in ("1", "true"):
            rows = debtors
        data = {
            "debtors": len(debtors),
            "debt_total": sum(r["debt"] for r in debtors),
            "rows": rows,
        }
        return Response(s.StudentListSerializer(data).data)


class StudentLedgerView(APIView):
    permission_classes = (IsAdmin,)

    @extend_schema(responses=s.AdminLedgerSerializer)
    def get(self, request: Request, pk: str) -> Response:
        student = get_object_or_404(_students(), pk=pk)
        return Response(s.AdminLedgerSerializer(_ledger(student, admin=True)).data)


class StudentDiscountView(APIView):
    permission_classes = (IsAdmin,)

    @extend_schema(request=s.DiscountWriteSerializer, responses={204: None})
    def put(self, request: Request, pk: str) -> Response:
        student = get_object_or_404(_students(), pk=pk)
        form = s.DiscountWriteSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        services.set_discount(request, student, form.validated_data["percent"])
        return Response(status=204)


class StudentPaymentsView(APIView):
    permission_classes = (IsAdmin,)

    @extend_schema(request=s.PaymentWriteSerializer, responses={201: s.AdminLedgerSerializer})
    def post(self, request: Request, pk: str) -> Response:
        student = get_object_or_404(_students(), pk=pk)
        form = s.PaymentWriteSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        services.record_payment(request, student, form.validated_data)
        return Response(s.AdminLedgerSerializer(_ledger(student, admin=True)).data, status=201)


class VoidChargeView(APIView):
    permission_classes = (IsAdmin,)

    @extend_schema(request=s.VoidWriteSerializer, responses={204: None})
    def post(self, request: Request, pk: str) -> Response:
        charge = get_object_or_404(Charge, pk=pk)
        form = s.VoidWriteSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        services.void(request, charge, form.validated_data["reason"])
        return Response(status=204)


class VoidPaymentView(APIView):
    permission_classes = (IsAdmin,)

    @extend_schema(request=s.VoidWriteSerializer, responses={204: None})
    def post(self, request: Request, pk: str) -> Response:
        payment = get_object_or_404(Payment, pk=pk)
        form = s.VoidWriteSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        services.void(request, payment, form.validated_data["reason"])
        return Response(status=204)


class MyPaymentsView(APIView):
    """The student's own account: charges, payments (voided ones hidden) and the debt."""

    permission_classes = STUDENT_PAGES

    @extend_schema(responses=s.LedgerSerializer)
    def get(self, request: Request) -> Response:
        return Response(s.LedgerSerializer(_ledger(subject_student(request), admin=False)).data)
