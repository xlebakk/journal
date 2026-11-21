"""Explicit fields; students get a reduced lesson view without internal ids and versions."""

from typing import Any

from rest_framework import serializers

from apps.academics.models import Course, LessonType, Room
from apps.accounts.models import Role, User

from .models import Lesson, ScheduleRequest, ScheduleSlot


def _name(source: str) -> Any:
    return serializers.CharField(source=source, read_only=True, default=None)


class SlotSerializer(serializers.ModelSerializer[ScheduleSlot]):
    group = serializers.UUIDField(source="course.group_id", read_only=True)
    group_name = serializers.CharField(source="course.group.name", read_only=True)
    subject_name = serializers.CharField(source="course.subject.name", read_only=True)
    subject_short = serializers.CharField(source="course.subject.short_name", read_only=True)
    teacher = serializers.UUIDField(source="course.teacher_id", read_only=True)
    teacher_name = serializers.CharField(source="course.teacher.short_name", read_only=True)
    room_name = _name("room.name")
    lesson_type_short = serializers.CharField(
        source="lesson_type.short", read_only=True, default=None
    )

    class Meta:
        model = ScheduleSlot
        fields: tuple[str, ...] = (
            "id",
            "course",
            "group",
            "group_name",
            "subject_name",
            "subject_short",
            "teacher",
            "teacher_name",
            "weekday",
            "start_time",
            "end_time",
            "room",
            "room_name",
            "lesson_type",
            "lesson_type_short",
            "valid_from",
            "valid_to",
        )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        def value(name: str) -> Any:
            return attrs.get(name, getattr(self.instance, name, None))

        if value("start_time") and value("end_time") and value("end_time") <= value("start_time"):
            raise serializers.ValidationError({"end_time": ["ends_before_start"]})
        if value("valid_to") and value("valid_from") and value("valid_to") < value("valid_from"):
            raise serializers.ValidationError({"valid_to": ["ends_before_start"]})
        course: Course | None = value("course")
        if course is not None and course.group.is_archived:
            raise serializers.ValidationError({"course": ["group_archived"]})
        if (
            self.instance is not None
            and "course" in attrs
            and attrs["course"] != self.instance.course
        ):
            raise serializers.ValidationError({"course": ["cannot_change_course"]})
        return attrs


class SlotWriteSerializer(SlotSerializer):
    confirm = serializers.BooleanField(default=False, write_only=True)

    class Meta(SlotSerializer.Meta):
        fields = (*SlotSerializer.Meta.fields, "confirm")


class LessonSerializer(serializers.ModelSerializer[Lesson]):
    """Admin and teacher view of a lesson in the schedule."""

    course = serializers.UUIDField(source="course_id", read_only=True)
    group = serializers.UUIDField(source="course.group_id", read_only=True)
    group_name = serializers.CharField(source="course.group.name", read_only=True)
    subject_name = serializers.CharField(source="course.subject.name", read_only=True)
    subject_short = serializers.CharField(source="course.subject.short_name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.short_name", read_only=True)
    course_teacher = serializers.UUIDField(source="course.teacher_id", read_only=True)
    course_teacher_name = serializers.CharField(source="course.teacher.short_name", read_only=True)
    room_name = _name("room.name")
    planned_room_name = serializers.CharField(
        source="planned_room.name", read_only=True, default=None
    )
    lesson_type_short = serializers.CharField(
        source="lesson_type.short", read_only=True, default=None
    )
    lesson_type_name = serializers.CharField(
        source="lesson_type.name", read_only=True, default=None
    )
    is_moved = serializers.BooleanField(read_only=True)
    is_room_changed = serializers.BooleanField(read_only=True)
    is_substituted = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = (
            "id",
            "course",
            "group",
            "group_name",
            "subject_name",
            "subject_short",
            "date",
            "start_time",
            "end_time",
            "room",
            "room_name",
            "teacher",
            "teacher_name",
            "course_teacher",
            "course_teacher_name",
            "lesson_type",
            "lesson_type_short",
            "lesson_type_name",
            "status",
            "cancel_reason",
            "is_extra",
            "is_moved",
            "is_room_changed",
            "is_substituted",
            "planned_date",
            "planned_start_time",
            "planned_end_time",
            "planned_room_name",
            "slot",
            "version",
        )
        read_only_fields = fields

    def get_is_substituted(self, lesson: Lesson) -> bool:
        return lesson.teacher_id != lesson.course.teacher_id


class StudentLessonSerializer(serializers.ModelSerializer[Lesson]):
    """What a student sees: no versions, no internal links, nothing about other students."""

    subject_name = serializers.CharField(source="course.subject.name", read_only=True)
    subject_short = serializers.CharField(source="course.subject.short_name", read_only=True)
    group_name = serializers.CharField(source="course.group.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)
    room_name = _name("room.name")
    planned_room_name = serializers.CharField(
        source="planned_room.name", read_only=True, default=None
    )
    lesson_type_short = serializers.CharField(
        source="lesson_type.short", read_only=True, default=None
    )
    lesson_type_name = serializers.CharField(
        source="lesson_type.name", read_only=True, default=None
    )
    is_moved = serializers.BooleanField(read_only=True)
    is_room_changed = serializers.BooleanField(read_only=True)
    is_substituted = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = (
            "id",
            "date",
            "start_time",
            "end_time",
            "subject_name",
            "subject_short",
            "group_name",
            "teacher_name",
            "room_name",
            "lesson_type_short",
            "lesson_type_name",
            "status",
            "cancel_reason",
            "is_extra",
            "is_moved",
            "is_room_changed",
            "is_substituted",
            "planned_date",
            "planned_start_time",
            "planned_end_time",
            "planned_room_name",
        )
        read_only_fields = fields

    def get_is_substituted(self, lesson: Lesson) -> bool:
        return lesson.teacher_id != lesson.course.teacher_id


class VersionSerializer(serializers.Serializer[Any]):
    version = serializers.IntegerField(min_value=1)


class CancelSerializer(VersionSerializer):
    reason = serializers.CharField(max_length=300)


class MoveSerializer(VersionSerializer):
    date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    room = serializers.PrimaryKeyRelatedField(
        queryset=Room.objects.filter(is_archived=False), allow_null=True
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError({"end_time": ["ends_before_start"]})
        return attrs


class SubstituteSerializer(VersionSerializer):
    teacher = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.with_role(Role.TEACHER).active(), allow_null=True
    )


class ExtraLessonSerializer(serializers.Serializer[Any]):
    course = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.select_related("group__academic_year", "teacher")
    )
    date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    room = serializers.PrimaryKeyRelatedField(
        queryset=Room.objects.filter(is_archived=False), allow_null=True, required=False
    )
    lesson_type = serializers.PrimaryKeyRelatedField(
        queryset=LessonType.objects.filter(is_archived=False), allow_null=True, required=False
    )
    teacher = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.with_role(Role.TEACHER).active(), allow_null=True, required=False
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError({"end_time": ["ends_before_start"]})
        if attrs["course"].group.is_archived:
            raise serializers.ValidationError({"course": ["group_archived"]})
        return attrs


class ScheduleRequestSerializer(serializers.ModelSerializer[ScheduleRequest]):
    author_name = serializers.CharField(source="author.short_name", read_only=True)
    lesson_info = LessonSerializer(source="lesson", read_only=True)
    proposed_room_name = serializers.CharField(
        source="proposed_room.name", read_only=True, default=None
    )
    resolved_by_name = serializers.CharField(
        source="resolved_by.short_name", read_only=True, default=None
    )

    class Meta:
        model = ScheduleRequest
        fields = (
            "id",
            "lesson",
            "lesson_info",
            "author_name",
            "kind",
            "proposed_date",
            "proposed_start_time",
            "proposed_end_time",
            "proposed_room",
            "proposed_room_name",
            "reason",
            "status",
            "resolved_by_name",
            "resolved_at",
            "resolution_comment",
            "created_at",
        )
        read_only_fields = (
            "id",
            "lesson",
            "lesson_info",
            "author_name",
            "proposed_room_name",
            "status",
            "resolved_by_name",
            "resolved_at",
            "resolution_comment",
            "created_at",
        )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs.get("kind") == ScheduleRequest.Kind.MOVE:
            missing = [
                name
                for name in ("proposed_date", "proposed_start_time", "proposed_end_time")
                if not attrs.get(name)
            ]
            if missing:
                raise serializers.ValidationError({name: ["required"] for name in missing})
            if attrs["proposed_end_time"] <= attrs["proposed_start_time"]:
                raise serializers.ValidationError({"proposed_end_time": ["ends_before_start"]})
        else:
            for name in (
                "proposed_date",
                "proposed_start_time",
                "proposed_end_time",
                "proposed_room",
            ):
                attrs.pop(name, None)
        return attrs


class ResolveSerializer(serializers.Serializer[Any]):
    comment = serializers.CharField(max_length=300, required=False, allow_blank=True)


class RoomOptionSerializer(serializers.ModelSerializer[Room]):
    class Meta:
        model = Room
        fields = ("id", "name", "capacity")
        read_only_fields = fields
