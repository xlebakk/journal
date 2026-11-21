"""What a student sees about themselves (SPEC §6). Nothing about other students, no internal
versions or authors' ids; the attendance comment is a staff note and is not shown."""

from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.schedule.serializers import StudentLessonSerializer

from .models import AttendanceStatus


class StudentGradeSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    date = serializers.DateField()
    course = serializers.UUIDField()
    subject_name = serializers.CharField()
    subject_short = serializers.CharField()
    group_name = serializers.CharField()
    topic = serializers.CharField(allow_blank=True)
    lesson_type_short = serializers.CharField(allow_null=True)
    value = serializers.IntegerField()
    work_type_name = serializers.CharField()
    weight = serializers.DecimalField(max_digits=4, decimal_places=2)
    comment = serializers.CharField(allow_blank=True)
    given_at = serializers.DateTimeField()
    low = serializers.BooleanField()


class SubjectSummarySerializer(serializers.Serializer[Any]):
    course = serializers.UUIDField()
    subject_name = serializers.CharField()
    group_name = serializers.CharField()
    teacher_name = serializers.CharField()
    average = serializers.DecimalField(max_digits=6, decimal_places=2, allow_null=True)
    attendance_percent = serializers.DecimalField(max_digits=6, decimal_places=2, allow_null=True)
    low = serializers.BooleanField()


class HomeworkSerializer(serializers.Serializer[Any]):
    lesson = serializers.UUIDField()
    subject_name = serializers.CharField()
    assigned_on = serializers.DateField()
    topic = serializers.CharField(allow_blank=True)
    homework = serializers.CharField()
    due_on = serializers.DateField(allow_null=True)


class StudentHomeSerializer(serializers.Serializer[Any]):
    today = serializers.DateField()
    period_name = serializers.CharField()
    lessons_today = StudentLessonSerializer(many=True)
    new_grades = StudentGradeSerializer(many=True)
    homework = HomeworkSerializer(many=True)
    subjects = SubjectSummarySerializer(many=True)


class DiaryGradeSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    value = serializers.IntegerField()
    work_type_name = serializers.CharField()
    weight = serializers.DecimalField(max_digits=4, decimal_places=2)
    comment = serializers.CharField(allow_blank=True)
    low = serializers.BooleanField()


class DiaryLessonSerializer(StudentLessonSerializer):
    topic = serializers.CharField(read_only=True)
    homework = serializers.CharField(read_only=True)
    attendance = serializers.SerializerMethodField()
    grades = serializers.SerializerMethodField()

    class Meta(StudentLessonSerializer.Meta):
        fields: tuple[str, ...] = (  # type: ignore[assignment]
            *StudentLessonSerializer.Meta.fields,
            "topic",
            "homework",
            "attendance",
            "grades",
        )
        read_only_fields = fields  # type: ignore[assignment]

    @extend_schema_field(serializers.ChoiceField(choices=AttendanceStatus.choices, allow_null=True))
    def get_attendance(self, lesson: Any) -> str | None:
        return self.context["attendance"].get(lesson.pk)  # type: ignore[no-any-return]

    @extend_schema_field(DiaryGradeSerializer(many=True))
    def get_grades(self, lesson: Any) -> list[dict[str, Any]]:
        return DiaryGradeSerializer(self.context["grades"].get(lesson.pk, []), many=True).data  # type: ignore[return-value]


class DiarySerializer(serializers.Serializer[Any]):
    week_start = serializers.DateField()
    today = serializers.DateField()
    lessons = DiaryLessonSerializer(many=True)


class TermBriefSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()


class CourseGradesSerializer(serializers.Serializer[Any]):
    course = serializers.UUIDField()
    subject_name = serializers.CharField()
    group_name = serializers.CharField()
    teacher_name = serializers.CharField()
    average = serializers.DecimalField(max_digits=6, decimal_places=2, allow_null=True)
    low = serializers.BooleanField()
    grades = StudentGradeSerializer(many=True)


class StudentGradesSerializer(serializers.Serializer[Any]):
    period_from = serializers.DateField()
    period_to = serializers.DateField()
    period = serializers.CharField()
    terms = TermBriefSerializer(many=True)
    scale = serializers.CharField()
    low_below = serializers.DecimalField(max_digits=6, decimal_places=2)
    courses = CourseGradesSerializer(many=True)


class CourseAttendanceSerializer(serializers.Serializer[Any]):
    course = serializers.UUIDField()
    subject_name = serializers.CharField()
    group_name = serializers.CharField()
    percent = serializers.DecimalField(max_digits=6, decimal_places=2, allow_null=True)
    present = serializers.IntegerField()
    late = serializers.IntegerField()
    absent = serializers.IntegerField()
    excused = serializers.IntegerField()
    eligible = serializers.IntegerField()


class DayMarkSerializer(serializers.Serializer[Any]):
    subject_short = serializers.CharField()
    subject_name = serializers.CharField()
    status = serializers.CharField()


class CalendarDaySerializer(serializers.Serializer[Any]):
    date = serializers.DateField()
    lessons = serializers.IntegerField()
    marks = DayMarkSerializer(many=True)


class StudentAttendanceSerializer(serializers.Serializer[Any]):
    period_from = serializers.DateField()
    period_to = serializers.DateField()
    threshold = serializers.IntegerField()
    overall = serializers.DecimalField(max_digits=6, decimal_places=2, allow_null=True)
    excused = serializers.IntegerField()
    courses = CourseAttendanceSerializer(many=True)
    month = serializers.CharField()
    days = CalendarDaySerializer(many=True)


class StudentProfileViewSerializer(serializers.Serializer[Any]):
    full_name = serializers.CharField()
    login = serializers.CharField()
    groups = serializers.ListField(child=serializers.CharField())
    school = serializers.CharField(allow_blank=True)
    school_grade = serializers.IntegerField(allow_null=True)
    target = serializers.CharField(allow_blank=True)
    target_score = serializers.IntegerField(allow_null=True)
