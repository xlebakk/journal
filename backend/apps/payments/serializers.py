from typing import Any

from rest_framework import serializers

from .models import PaymentMethod

ENTRY_KINDS = [("charge", "charge"), ("payment", "payment")]


class GroupFeeRowSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    year_name = serializers.CharField()
    is_archived = serializers.BooleanField()
    members_count = serializers.IntegerField()
    monthly_amount = serializers.IntegerField()


class GroupFeesSerializer(serializers.Serializer[Any]):
    month = serializers.DateField()
    month_charges = serializers.IntegerField()
    groups = GroupFeeRowSerializer(many=True)


class GroupFeeWriteSerializer(serializers.Serializer[Any]):
    monthly_amount = serializers.IntegerField(min_value=0, max_value=100_000_000)


class BillWriteSerializer(serializers.Serializer[Any]):
    month = serializers.DateField()


class BillResultSerializer(serializers.Serializer[Any]):
    created = serializers.IntegerField()
    existing = serializers.IntegerField()


class StudentRowSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    full_name = serializers.CharField()
    login = serializers.CharField()
    groups = serializers.ListField(child=serializers.CharField())
    discount_percent = serializers.IntegerField()
    charged = serializers.IntegerField()
    paid = serializers.IntegerField()
    debt = serializers.IntegerField()


class StudentListSerializer(serializers.Serializer[Any]):
    debtors = serializers.IntegerField()
    debt_total = serializers.IntegerField()
    rows = StudentRowSerializer(many=True)


class EntrySerializer(serializers.Serializer[Any]):
    kind = serializers.ChoiceField(choices=ENTRY_KINDS)
    id = serializers.UUIDField()
    date = serializers.DateField()
    amount = serializers.IntegerField()
    group_name = serializers.CharField(allow_blank=True)
    full_amount = serializers.IntegerField(allow_null=True)
    discount_percent = serializers.IntegerField(allow_null=True)
    method = serializers.CharField(allow_blank=True)
    comment = serializers.CharField(allow_blank=True)


class AdminEntrySerializer(EntrySerializer):
    voided = serializers.BooleanField()
    void_reason = serializers.CharField(allow_blank=True)
    author_name = serializers.CharField(allow_blank=True)


class LedgerSerializer(serializers.Serializer[Any]):
    charged = serializers.IntegerField()
    paid = serializers.IntegerField()
    debt = serializers.IntegerField()
    discount_percent = serializers.IntegerField()
    entries = EntrySerializer(many=True)


class AdminLedgerSerializer(serializers.Serializer[Any]):
    student = serializers.UUIDField()
    full_name = serializers.CharField()
    login = serializers.CharField()
    charged = serializers.IntegerField()
    paid = serializers.IntegerField()
    debt = serializers.IntegerField()
    discount_percent = serializers.IntegerField()
    entries = AdminEntrySerializer(many=True)


class DiscountWriteSerializer(serializers.Serializer[Any]):
    percent = serializers.IntegerField(min_value=0, max_value=100)


class PaymentWriteSerializer(serializers.Serializer[Any]):
    amount = serializers.IntegerField(min_value=1, max_value=1_000_000_000)
    paid_on = serializers.DateField()
    method = serializers.ChoiceField(choices=PaymentMethod.choices)
    comment = serializers.CharField(required=False, allow_blank=True, default="", max_length=300)


class VoidWriteSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(max_length=300)
