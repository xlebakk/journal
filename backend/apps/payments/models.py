"""Payments (SPEC §16.3, stage 12): a monthly price per group, a discount per student.

Amounts are whole soʻm. A charge is made for every month the student spent at least one day in
a priced group; it keeps the price and the discount of the moment, so later changes do not
rewrite history. Mistakes are voided with a reason, never deleted.
"""

import uuid
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.academics.models import Group


class GroupFee(models.Model):
    group = models.OneToOneField(
        Group, on_delete=models.PROTECT, primary_key=True, related_name="fee"
    )
    monthly_amount = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints: ClassVar = [
            models.CheckConstraint(condition=Q(monthly_amount__gt=0), name="payments_fee_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.group}: {self.monthly_amount}"


class StudentDiscount(models.Model):
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        primary_key=True,
        related_name="discount",
    )
    percent = models.PositiveSmallIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints: ClassVar = [
            models.CheckConstraint(
                condition=Q(percent__gt=0, percent__lte=100), name="payments_discount_range"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student}: {self.percent}%"


class Voidable(models.Model):
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    void_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        abstract = True


class Charge(Voidable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="charges"
    )
    group = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="charges")
    month = models.DateField(help_text="The first day of the month.")
    full_amount = models.PositiveIntegerField()
    discount_percent = models.PositiveSmallIntegerField(default=0)
    amount = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )

    class Meta:
        constraints: ClassVar = [
            # A voided charge stays: billing the month again does not bring it back.
            models.UniqueConstraint(
                fields=["student", "group", "month"], name="payments_charge_once_a_month"
            ),
            models.CheckConstraint(condition=Q(month__day=1), name="payments_charge_month_start"),
            models.CheckConstraint(
                condition=Q(discount_percent__lte=100) & Q(amount__lte=models.F("full_amount")),
                name="payments_charge_amounts",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student} {self.group} {self.month:%Y-%m}"


class PaymentMethod(models.TextChoices):
    CASH = "cash", "наличные"
    CARD = "card", "карта"
    TRANSFER = "transfer", "перевод"


class Payment(Voidable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments"
    )
    amount = models.PositiveIntegerField()
    paid_on = models.DateField()
    method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    comment = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        constraints: ClassVar = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payments_payment_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.student} {self.amount} {self.paid_on}"
