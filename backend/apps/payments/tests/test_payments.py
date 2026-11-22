"""Payments (SPEC §16.3, stage 12): monthly price per group, a discount per student."""

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.academics.models import Group
from apps.accounts.models import Role, User
from apps.audit.models import AuditLog
from apps.payments.models import Charge
from apps.payments.services import discounted
from conftest import MakeUser, enroll

ClientFor = Callable[..., APIClient]
OCTOBER = "2026-10-01"


def bill(client: APIClient, month: str = OCTOBER) -> Any:
    return client.post("/api/v1/admin/payments/bill", {"month": month}, format="json")


def set_fee(client: APIClient, group: Group, amount: int) -> None:
    response = client.put(
        f"/api/v1/admin/payments/groups/{group.pk}", {"monthly_amount": amount}, format="json"
    )
    assert response.status_code == 204


def ledger(client: APIClient, student: User) -> Any:
    return client.get(f"/api/v1/admin/payments/students/{student.pk}").json()


def pay(client: APIClient, student: User, amount: int, **extra: Any) -> Any:
    body = {"amount": amount, "paid_on": "2026-10-05", "method": "cash", **extra}
    return client.post(
        f"/api/v1/admin/payments/students/{student.pk}/payments", body, format="json"
    )


def test_discount_rounds_half_up() -> None:
    assert discounted(450_000, 15) == 382_500
    assert discounted(333_333, 10) == 300_000  # 299 999.7
    assert discounted(500_000, 100) == 0


@pytest.mark.django_db
class TestBilling:
    def test_month_charges_members_with_price_minus_discount(
        self, group: Group, student: User, make_user: MakeUser, admin_client: APIClient
    ) -> None:
        enroll(group, student)
        sister = make_user(Role.STUDENT)
        enroll(group, sister, joined=date(2026, 10, 20))  # a few days of October: a full month
        gone = make_user(Role.STUDENT)
        enroll(group, gone, left=date(2026, 9, 30))
        set_fee(admin_client, group, 500_000)
        response = admin_client.put(
            f"/api/v1/admin/payments/students/{sister.pk}/discount", {"percent": 10}, format="json"
        )
        assert response.status_code == 204

        assert bill(admin_client).json() == {"created": 2, "existing": 0}
        assert bill(admin_client).json() == {"created": 0, "existing": 2}  # safe to repeat
        amounts = dict(Charge.objects.values_list("student_id", "amount"))
        assert amounts == {student.pk: 500_000, sister.pk: 450_000}
        assert AuditLog.objects.filter(action="billing.run").count() == 2

    def test_rules(self, group: Group, admin_client: APIClient) -> None:
        set_fee(admin_client, group, 500_000)
        assert bill(admin_client, "2099-01-01").json() == {"detail": ["month_in_future"]}
        assert bill(admin_client, "2026-10-15").json() == {"detail": ["invalid_month"]}

    def test_price_change_and_removal_do_not_touch_old_charges(
        self, group: Group, student: User, admin_client: APIClient
    ) -> None:
        enroll(group, student)
        set_fee(admin_client, group, 400_000)
        bill(admin_client, "2026-09-01")
        set_fee(admin_client, group, 450_000)
        bill(admin_client)
        set_fee(admin_client, group, 0)  # no longer billed
        assert bill(admin_client, "2026-11-01").json()["created"] == 0
        assert ledger(admin_client, student)["charged"] == 850_000
        actions = list(AuditLog.objects.filter(action="fee.update").values_list("after", flat=True))
        assert {"monthly_amount": 450_000} in actions


@pytest.mark.django_db
class TestPayments:
    def test_payments_reduce_the_debt_and_voids_restore_it(
        self, group: Group, student: User, admin_client: APIClient
    ) -> None:
        enroll(group, student)
        set_fee(admin_client, group, 500_000)
        bill(admin_client)
        assert pay(admin_client, student, 300_000, comment="за октябрь").status_code == 201
        body = ledger(admin_client, student)
        assert (body["charged"], body["paid"], body["debt"]) == (500_000, 300_000, 200_000)
        payment = next(e for e in body["entries"] if e["kind"] == "payment")
        assert payment["author_name"]

        url = f"/api/v1/admin/payments/payments/{payment['id']}/void"
        assert admin_client.post(url, {"reason": ""}, format="json").status_code == 400
        assert admin_client.post(url, {"reason": "ошибка суммы"}, format="json").status_code == 204
        again = admin_client.post(url, {"reason": "ещё раз"}, format="json")
        assert again.json() == {"detail": ["already_voided"]}
        assert ledger(admin_client, student)["debt"] == 500_000
        assert AuditLog.objects.get(action="payment.void").reason == "ошибка суммы"

    def test_voided_charge_is_not_billed_again(
        self, group: Group, student: User, admin_client: APIClient
    ) -> None:
        enroll(group, student)
        set_fee(admin_client, group, 500_000)
        bill(admin_client)
        charge = Charge.objects.get()
        response = admin_client.post(
            f"/api/v1/admin/payments/charges/{charge.pk}/void",
            {"reason": "болел весь месяц"},
            format="json",
        )
        assert response.status_code == 204
        assert bill(admin_client).json() == {"created": 0, "existing": 1}
        assert ledger(admin_client, student)["debt"] == 0

    def test_rules(self, student: User, admin_client: APIClient) -> None:
        assert pay(admin_client, student, 0).status_code == 400
        assert pay(admin_client, student, 100, paid_on="2099-01-01").json() == {
            "detail": ["paid_in_future"]
        }
        assert pay(admin_client, student, 100, method="crypto").status_code == 400

    def test_debtors_list(
        self, group: Group, student: User, make_user: MakeUser, admin_client: APIClient
    ) -> None:
        enroll(group, student)
        paid_up = make_user(Role.STUDENT)
        enroll(group, paid_up)
        set_fee(admin_client, group, 500_000)
        bill(admin_client)
        pay(admin_client, paid_up, 500_000)
        body = admin_client.get("/api/v1/admin/payments/students", {"debtors": "1"}).json()
        assert (body["debtors"], body["debt_total"]) == (1, 500_000)
        assert [r["full_name"] for r in body["rows"]] == [student.full_name]
        assert body["rows"][0]["groups"] == [group.name]


@pytest.mark.django_db
class TestAccess:
    def test_student_sees_own_account_without_voided_entries(
        self,
        group: Group,
        student: User,
        make_user: MakeUser,
        admin_client: APIClient,
        client_for: ClientFor,
    ) -> None:
        enroll(group, student)
        set_fee(admin_client, group, 500_000)
        bill(admin_client)
        pay(admin_client, student, 100_000)
        wrong = pay(admin_client, student, 999).json()["entries"]
        wrong_id = next(e["id"] for e in wrong if e["amount"] == 999)
        admin_client.post(
            f"/api/v1/admin/payments/payments/{wrong_id}/void",
            {"reason": "опечатка"},
            format="json",
        )
        body = client_for(student).get("/api/v1/student/payments").json()
        assert body["debt"] == 400_000
        assert [e["amount"] for e in body["entries"]] == [100_000, 500_000]
        assert "void_reason" not in body["entries"][0]
        assert "author_name" not in body["entries"][0]
        assert "student" not in body

    def test_teachers_and_students_have_no_admin_access(
        self, student: User, teacher: User, client_for: ClientFor
    ) -> None:
        for user in (teacher, student):
            client = client_for(user)
            assert client.get("/api/v1/admin/payments/students").status_code == 403
            assert pay(client, student, 100).status_code == 403
        assert client_for(teacher).get("/api/v1/student/payments").status_code == 403

    def test_ledger_of_a_non_student_is_404(self, teacher: User, admin_client: APIClient) -> None:
        assert admin_client.get(f"/api/v1/admin/payments/students/{teacher.pk}").status_code == 404
