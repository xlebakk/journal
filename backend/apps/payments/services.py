"""Every change of money goes through here: one transaction, one audit record.

* `bill_month` charges every student for each priced group they spent at least one day in
  during the month: the group's price minus the student's discount, rounded to whole soʻm.
  It is safe to run twice — a charge exists once per student, group and month, voided or not.
* The balance is computed here only: debt = charged − paid, voided entries excluded.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.request import Request

from apps.academics.models import Group, GroupMembership
from apps.accounts.models import User
from apps.accounts.permissions import current_user
from apps.audit import services as audit
from apps.journal.services import Rule

from .models import Charge, GroupFee, Payment, StudentDiscount


def month_start(day: date) -> date:
    return day.replace(day=1)


def month_end(first: date) -> date:
    return (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def discounted(full: int, percent: int) -> int:
    """Half up, in whole soʻm: 450 000 with 15% → 382 500."""
    return (full * (100 - percent) + 50) // 100


@dataclass(frozen=True)
class Balance:
    charged: int
    paid: int

    @property
    def debt(self) -> int:
        return self.charged - self.paid


def balances(students: list[Any]) -> dict[Any, Balance]:
    """Two aggregate queries for any number of students."""
    charged = dict(
        Charge.objects.filter(student__in=students, voided_at__isnull=True)
        .values("student")
        .annotate(total=Sum("amount"))
        .values_list("student", "total")
    )
    paid = dict(
        Payment.objects.filter(student__in=students, voided_at__isnull=True)
        .values("student")
        .annotate(total=Sum("amount"))
        .values_list("student", "total")
    )
    return {s: Balance(charged.get(s, 0) or 0, paid.get(s, 0) or 0) for s in students}


def balance(student: User) -> Balance:
    return balances([student.pk])[student.pk]


def discount_of(student: User) -> int:
    found = StudentDiscount.objects.filter(student=student).first()
    return found.percent if found else 0


def bill_month(request: Request, first: date) -> dict[str, int]:
    if first != month_start(first):
        raise Rule("invalid_month")
    if first > month_start(timezone.localdate()):
        raise Rule("month_in_future")
    last = month_end(first)
    discounts = dict(StudentDiscount.objects.values_list("student_id", "percent"))
    created = existing = 0
    with transaction.atomic():
        fees = GroupFee.objects.select_related("group").select_for_update()
        for fee in fees:
            members = (
                GroupMembership.objects.filter(group=fee.group, joined_on__lte=last)
                .filter(Q(left_on__isnull=True) | Q(left_on__gte=first))
                .values_list("student_id", flat=True)
                .distinct()
            )
            done = set(
                Charge.objects.filter(group=fee.group, month=first).values_list(
                    "student_id", flat=True
                )
            )
            new = []
            for student_id in members:
                if student_id in done:
                    existing += 1
                    continue
                percent = discounts.get(student_id, 0)
                new.append(
                    Charge(
                        student_id=student_id,
                        group=fee.group,
                        month=first,
                        full_amount=fee.monthly_amount,
                        discount_percent=percent,
                        amount=discounted(fee.monthly_amount, percent),
                        created_by=current_user(request),
                    )
                )
            Charge.objects.bulk_create(new)
            created += len(new)
        audit.record(
            request=request,
            action="billing.run",
            entity_type="payments.charge",
            after={"month": first.isoformat(), "created": created, "existing": existing},
        )
    return {"created": created, "existing": existing}


def set_group_fee(request: Request, group: Group, amount: int) -> None:
    """0 removes the price: the group is no longer billed (past charges stay)."""
    with transaction.atomic():
        fee = GroupFee.objects.select_for_update().filter(group=group).first()
        before = {"monthly_amount": fee.monthly_amount} if fee else None
        if amount == 0:
            if fee is None:
                return
            fee.delete()
            after = None
        else:
            GroupFee.objects.update_or_create(group=group, defaults={"monthly_amount": amount})
            after = {"monthly_amount": amount}
        audit.record(
            request=request,
            action="fee.update",
            entity=group,
            before=before,
            after=after,
        )


def set_discount(request: Request, student: User, percent: int) -> None:
    """Applies to the next charges; existing ones keep their discount."""
    if not 0 <= percent <= 100:
        raise Rule("discount_range")
    with transaction.atomic():
        current = StudentDiscount.objects.select_for_update().filter(student=student).first()
        before = {"percent": current.percent} if current else {"percent": 0}
        if percent == 0:
            if current:
                current.delete()
        else:
            StudentDiscount.objects.update_or_create(student=student, defaults={"percent": percent})
        audit.record(
            request=request,
            action="discount.update",
            entity=student,
            before=before,
            after={"percent": percent},
        )


def record_payment(request: Request, student: User, data: dict[str, Any]) -> Payment:
    if data["paid_on"] > timezone.localdate():
        raise Rule("paid_in_future")
    with transaction.atomic():
        payment = Payment.objects.create(student=student, created_by=current_user(request), **data)
        audit.record(
            request=request,
            action="payment.create",
            entity=payment,
            after={
                "student": str(student.pk),
                "amount": payment.amount,
                "paid_on": payment.paid_on.isoformat(),
                "method": payment.method,
                "comment": payment.comment,
            },
        )
    return payment


def void(request: Request, entry: Charge | Payment, reason: str) -> None:
    reason = reason.strip()
    if not reason:
        raise Rule("reason_required")
    kind = "charge" if isinstance(entry, Charge) else "payment"
    with transaction.atomic():
        locked = type(entry).objects.select_for_update().get(pk=entry.pk)
        if locked.voided_at is not None:
            raise Rule("already_voided")
        locked.voided_at = timezone.now()
        locked.voided_by = current_user(request)
        locked.void_reason = reason
        locked.save(update_fields=["voided_at", "voided_by", "void_reason"])
        audit.record(
            request=request,
            action=f"{kind}.void",
            entity=locked,
            before={"amount": locked.amount, "voided": False},
            after={"amount": locked.amount, "voided": True},
            reason=reason,
        )
