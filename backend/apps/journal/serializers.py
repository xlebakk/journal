"""Explicit fields everywhere. The journal is read by staff only (students get their own,
reduced view in stage 4)."""

from typing import Any

from rest_framework import serializers

from apps.academics.models import LessonType, WorkType

from .models import Attendance, AttendanceStatus, Grade


class AttendanceSerializer(serializers.ModelSerializer[Attendance]):
    lesson = serializers.UUIDField(source="lesson_id", read_only=True)
    student = serializers.UUIDField(source="student_id", read_only=True)

    class Meta:
        model = Attendance
        fields = ("id", "lesson", "student", "status", "late_minutes", "comment", "version")
        read_only_fields = fields


class GradeSerializer(serializers.ModelSerializer[Grade]):
    lesson = serializers.UUIDField(source="lesson_id", read_only=True)
    student = serializers.UUIDField(source="student_id", read_only=True)
    work_type = serializers.UUIDField(source="work_type_id", read_only=True)
    mine = serializers.SerializerMethodField()
    author_name = serializers.CharField(source="created_by.short_name", read_only=True)

    class Meta:
        model = Grade
        fields = (
            "id",
            "lesson",
            "student",
            "value",
            "work_type",
            "weight",
            "comment",
            "position",
            "mine",
            "author_name",
            "version",
        )
        read_only_fields = fields

    def get_mine(self, grade: Grade) -> bool:
        return grade.created_by_id == self.context.get("user_id")


class WorkTypeOptionSerializer(serializers.ModelSerializer[WorkType]):
    class Meta:
        model = WorkType
        fields = ("id", "name", "weight")
        read_only_fields = fields


class LessonTypeOptionSerializer(serializers.ModelSerializer[LessonType]):
    class Meta:
        model = LessonType
        fields = ("id", "name", "short", "default_work_type", "counts_attendance")
        read_only_fields = fields


class StatsSerializer(serializers.Serializer[Any]):
    average = serializers.DecimalField(max_digits=6, decimal_places=2, allow_null=True)
    grades = serializers.IntegerField()
    attendance_percent = serializers.DecimalField(max_digits=6, decimal_places=2, allow_null=True)
    present = serializers.IntegerField()
    late = serializers.IntegerField()
    absent = serializers.IntegerField()
    excused = serializers.IntegerField()
    eligible = serializers.IntegerField()


class PeriodSerializer(serializers.Serializer[Any]):
    start = serializers.DateField()
    end = serializers.DateField(allow_null=True)


class RowStudentSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    short_name = serializers.CharField()
    full_name = serializers.CharField()
    periods = PeriodSerializer(many=True)
    stats = StatsSerializer()


class GridLessonSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    date = serializers.DateField()
    start_time = serializers.TimeField()
    lesson_type = serializers.UUIDField(allow_null=True)
    lesson_type_short = serializers.CharField(allow_null=True)
    lesson_type_name = serializers.CharField(allow_null=True)
    topic = serializers.CharField(allow_blank=True)
    homework = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    version = serializers.IntegerField()
    editable = serializers.BooleanField()
    needs_reason = serializers.BooleanField()
    locked = serializers.CharField(allow_null=True)


class CourseInfoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    group_name = serializers.CharField()
    subject_name = serializers.CharField()
    teacher_name = serializers.CharField()
    year_name = serializers.CharField()
    scale = serializers.CharField()


class JournalRulesSerializer(serializers.Serializer[Any]):
    scale = serializers.CharField()
    low_below = serializers.DecimalField(max_digits=6, decimal_places=2)
    max_grades = serializers.IntegerField()
    edit_window_days = serializers.IntegerField()


class GridSerializer(serializers.Serializer[Any]):
    course = CourseInfoSerializer()
    period_from = serializers.DateField()
    period_to = serializers.DateField()
    today = serializers.DateField()
    rules = JournalRulesSerializer()
    lessons = GridLessonSerializer(many=True)
    students = RowStudentSerializer(many=True)
    attendance = AttendanceSerializer(many=True)
    grades = GradeSerializer(many=True)
    work_types = WorkTypeOptionSerializer(many=True)


class LessonPageSerializer(serializers.Serializer[Any]):
    course = CourseInfoSerializer()
    today = serializers.DateField()
    rules = JournalRulesSerializer()
    lesson = GridLessonSerializer()
    comment = serializers.CharField(allow_blank=True)
    end_time = serializers.TimeField()
    room_name = serializers.CharField(allow_null=True)
    teacher_name = serializers.CharField()
    window_closes_on = serializers.DateField()
    students = RowStudentSerializer(many=True)
    attendance = AttendanceSerializer(many=True)
    grades = GradeSerializer(many=True)
    work_types = WorkTypeOptionSerializer(many=True)
    lesson_types = LessonTypeOptionSerializer(many=True)
    topic_suggestions = serializers.ListField(child=serializers.CharField())


class CourseOptionSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    group_name = serializers.CharField()
    subject = serializers.UUIDField()
    subject_name = serializers.CharField()
    teacher_name = serializers.CharField()
    year = serializers.UUIDField()


class TermOptionSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()


# --- Writes --------------------------------------------------------------------------------


class ReasonMixin(serializers.Serializer[Any]):
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class LessonUpdateSerializer(ReasonMixin):
    version = serializers.IntegerField(min_value=1)
    topic = serializers.CharField(max_length=300, required=False, allow_blank=True)
    homework = serializers.CharField(max_length=5000, required=False, allow_blank=True)
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    lesson_type = serializers.PrimaryKeyRelatedField(
        queryset=LessonType.objects.filter(is_archived=False), required=False, allow_null=True
    )


class VersionReasonSerializer(ReasonMixin):
    version = serializers.IntegerField(min_value=1)


class AttendanceWriteSerializer(ReasonMixin):
    status = serializers.ChoiceField(choices=AttendanceStatus.choices)
    late_minutes = serializers.IntegerField(
        min_value=1, max_value=300, required=False, allow_null=True
    )
    comment = serializers.CharField(max_length=300, required=False, allow_blank=True)
    version = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class GradeCreateSerializer(ReasonMixin):
    student = serializers.UUIDField()
    value = serializers.IntegerField()
    work_type = serializers.UUIDField(required=False, allow_null=True)
    comment = serializers.CharField(max_length=300, required=False, allow_blank=True)


class GradeUpdateSerializer(ReasonMixin):
    version = serializers.IntegerField(min_value=1)
    value = serializers.IntegerField(required=False)
    work_type = serializers.UUIDField(required=False)
    comment = serializers.CharField(max_length=300, required=False, allow_blank=True)


class TodayLessonSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    group_name = serializers.CharField()
    subject_name = serializers.CharField()
    room_name = serializers.CharField(allow_null=True)
    status = serializers.CharField()
    state = serializers.ChoiceField(choices=["upcoming", "to_fill", "filled", "cancelled"])
    is_substituted = serializers.BooleanField()


class AttentionSerializer(serializers.Serializer[Any]):
    student = serializers.UUIDField()
    student_name = serializers.CharField()
    course = serializers.UUIDField()
    group_name = serializers.CharField()
    subject_name = serializers.CharField()
    reason = serializers.ChoiceField(choices=["attendance", "low_grades"])
    attendance_percent = serializers.DecimalField(max_digits=6, decimal_places=2, allow_null=True)
    grades = serializers.ListField(child=serializers.IntegerField())


class TodaySerializer(serializers.Serializer[Any]):
    today = serializers.DateField()
    lessons = TodayLessonSerializer(many=True)
    unfilled = TodayLessonSerializer(many=True)
    attention = AttentionSerializer(many=True)
