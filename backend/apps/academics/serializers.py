from typing import Any

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import Role, User
from apps.core.serializers import DatabaseUniqueModelSerializer
from apps.journal.models import Grade

from .models import (
    AcademicYear,
    Course,
    Group,
    GroupMembership,
    Holiday,
    LessonType,
    Room,
    Subject,
    Term,
    WorkType,
    members_on,
)


class PersonSerializer(serializers.ModelSerializer[User]):
    full_name = serializers.CharField(read_only=True)
    short_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "full_name", "short_name")
        read_only_fields = fields


class AcademicYearSerializer(DatabaseUniqueModelSerializer[AcademicYear]):
    class Meta:
        model = AcademicYear
        fields = ("id", "name", "starts_on", "ends_on", "is_current", "grade_scale")

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        starts = attrs.get("starts_on", getattr(self.instance, "starts_on", None))
        ends = attrs.get("ends_on", getattr(self.instance, "ends_on", None))
        if starts and ends and ends <= starts:
            raise serializers.ValidationError({"ends_on": ["ends_before_start"]})
        scale_changes = self.instance is not None and attrs.get("grade_scale") not in (
            None,
            self.instance.grade_scale,
        )
        if (
            scale_changes
            and Grade.objects.filter(lesson__course__group__academic_year=self.instance).exists()
        ):
            # The scale is fixed once the year has grades.
            raise serializers.ValidationError({"grade_scale": ["scale_locked"]})
        return attrs

    def save(self, **kwargs: Any) -> AcademicYear:
        # Only one current year: unset the others in the same transaction.
        if self.validated_data.get("is_current"):
            qs = AcademicYear.objects.filter(is_current=True)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            qs.update(is_current=False)
        return super().save(**kwargs)


class TermSerializer(DatabaseUniqueModelSerializer[Term]):
    class Meta:
        model = Term
        fields = ("id", "year", "name", "starts_on", "ends_on")

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        year: AcademicYear | None = attrs.get("year", getattr(self.instance, "year", None))
        starts = attrs.get("starts_on", getattr(self.instance, "starts_on", None))
        ends = attrs.get("ends_on", getattr(self.instance, "ends_on", None))
        if starts and ends and ends < starts:
            raise serializers.ValidationError({"ends_on": ["ends_before_start"]})
        if year and starts and ends and not (year.contains(starts) and year.contains(ends)):
            raise serializers.ValidationError({"starts_on": ["outside_year"]})
        return attrs


class SubjectSerializer(DatabaseUniqueModelSerializer[Subject]):
    class Meta:
        model = Subject
        fields = ("id", "name", "short_name", "is_archived")

    def validate_short_name(self, value: str) -> str:
        value = value.strip()
        if not 2 <= len(value) <= 6:
            raise serializers.ValidationError("short_name_length")
        return value


class RoomSerializer(DatabaseUniqueModelSerializer[Room]):
    class Meta:
        model = Room
        fields = ("id", "name", "capacity", "is_archived")


class WorkTypeSerializer(DatabaseUniqueModelSerializer[WorkType]):
    class Meta:
        model = WorkType
        fields = ("id", "name", "weight", "is_archived")

    def validate_weight(self, value: Any) -> Any:
        if not 0 < value <= 10:
            raise serializers.ValidationError("weight_range")
        return value


class LessonTypeSerializer(DatabaseUniqueModelSerializer[LessonType]):
    class Meta:
        model = LessonType
        fields = (
            "id",
            "name",
            "short",
            "default_work_type",
            "counts_attendance",
            "sort_order",
            "is_archived",
        )


class HolidaySerializer(DatabaseUniqueModelSerializer[Holiday]):
    class Meta:
        model = Holiday
        fields = ("id", "date", "name")


class CourseBriefSerializer(DatabaseUniqueModelSerializer[Course]):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_short = serializers.CharField(source="subject.short_name", read_only=True)
    teacher = PersonSerializer(read_only=True)

    class Meta:
        model = Course
        fields = ("id", "subject", "subject_name", "subject_short", "teacher")
        read_only_fields = fields


class GroupSerializer(DatabaseUniqueModelSerializer[Group]):
    members_count = serializers.IntegerField(read_only=True, default=0)
    year_name = serializers.CharField(source="academic_year.name", read_only=True)
    courses = CourseBriefSerializer(many=True, read_only=True)

    class Meta:
        model = Group
        fields = (
            "id",
            "name",
            "academic_year",
            "year_name",
            "level",
            "is_archived",
            "members_count",
            "courses",
        )


def with_members_count(qs: Any) -> Any:
    day = timezone.localdate()
    return qs.annotate(
        members_count=Count(
            "memberships",
            filter=Q(memberships__joined_on__lte=day)
            & (Q(memberships__left_on__isnull=True) | Q(memberships__left_on__gte=day)),
            distinct=True,
        )
    )


class MembershipSerializer(DatabaseUniqueModelSerializer[GroupMembership]):
    student = PersonSerializer(read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = GroupMembership
        fields = ("id", "group", "group_name", "student", "joined_on", "left_on", "is_active")
        read_only_fields = ("id", "group", "group_name", "student", "is_active")

    def get_is_active(self, membership: GroupMembership) -> bool:
        return membership.active_on(timezone.localdate())

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        joined = attrs.get("joined_on", getattr(self.instance, "joined_on", None))
        left = attrs.get("left_on", getattr(self.instance, "left_on", None))
        if joined and left and left < joined:
            raise serializers.ValidationError({"left_on": ["left_before_joined"]})
        return attrs


class AddMemberSerializer(serializers.Serializer[Any]):
    student = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.with_role(Role.STUDENT).filter(archived_at__isnull=True)
    )
    joined_on = serializers.DateField()


class TransferSerializer(serializers.Serializer[Any]):
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.filter(is_archived=False))
    date = serializers.DateField()


class LeaveSerializer(serializers.Serializer[Any]):
    left_on = serializers.DateField()


def _teachers() -> Any:
    return User.objects.with_role(Role.TEACHER).filter(is_active=True, archived_at__isnull=True)


class CourseSerializer(DatabaseUniqueModelSerializer[Course]):
    teacher = serializers.PrimaryKeyRelatedField(queryset=_teachers())
    assistants = serializers.PrimaryKeyRelatedField(queryset=_teachers(), many=True, required=False)
    group_name = serializers.CharField(source="group.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_short = serializers.CharField(source="subject.short_name", read_only=True)
    teacher_info = PersonSerializer(source="teacher", read_only=True)
    assistants_info = PersonSerializer(source="assistants", many=True, read_only=True)

    class Meta:
        model = Course
        fields = (
            "id",
            "group",
            "group_name",
            "subject",
            "subject_name",
            "subject_short",
            "teacher",
            "teacher_info",
            "assistants",
            "assistants_info",
        )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        group = attrs.get("group", getattr(self.instance, "group", None))
        if group is not None and group.is_archived:
            raise serializers.ValidationError({"group": ["group_archived"]})
        teacher = attrs.get("teacher", getattr(self.instance, "teacher", None))
        if teacher is not None and teacher in attrs.get("assistants", []):
            raise serializers.ValidationError({"assistants": ["teacher_is_assistant"]})
        if self.instance is not None and "group" in attrs and attrs["group"] != self.instance.group:
            raise serializers.ValidationError({"group": ["cannot_change_group"]})
        return attrs


def current_groups_of(student: User) -> list[dict[str, str]]:
    day = timezone.localdate()
    return [
        {"id": str(m.group_id), "name": m.group.name}
        for m in GroupMembership.objects.filter(members_on(day), student=student)
        .select_related("group")
        .order_by("group__name")
    ]
