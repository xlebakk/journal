from typing import Any

from rest_framework import serializers

from apps.academics.models import GradeScale

Dec = serializers.DecimalField


def dec(places: int = 2) -> Any:
    return Dec(max_digits=7, decimal_places=places, allow_null=True)


class StatsFields(serializers.Serializer[Any]):
    average = dec()
    grades = serializers.IntegerField()
    attendance_percent = dec()
    present = serializers.IntegerField()
    late = serializers.IntegerField()
    absent = serializers.IntegerField()
    excused = serializers.IntegerField()
    eligible = serializers.IntegerField()


class CourseSummarySerializer(serializers.Serializer[Any]):
    students = serializers.IntegerField()
    average = dec()
    attendance_percent = dec()
    low_attendance = serializers.IntegerField()
    low_average = serializers.IntegerField()


class StatementCourseSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    group_name = serializers.CharField()
    subject_name = serializers.CharField()
    teacher_name = serializers.CharField()
    scale = serializers.ChoiceField(choices=GradeScale.choices)


class StatementRowSerializer(StatsFields):
    student = serializers.UUIDField()
    full_name = serializers.CharField()


class CourseStatementSerializer(serializers.Serializer[Any]):
    course = StatementCourseSerializer()
    first = serializers.DateField()
    last = serializers.DateField()
    rows = StatementRowSerializer(many=True)
    summary = CourseSummarySerializer()


class PerformanceCourseSerializer(CourseSummarySerializer):
    course = serializers.UUIDField()
    group_name = serializers.CharField()
    subject_name = serializers.CharField()
    teacher_name = serializers.CharField()


class PerformanceCellSerializer(serializers.Serializer[Any]):
    course = serializers.UUIDField()
    average = dec()
    attendance_percent = dec()


class PerformanceStudentSerializer(serializers.Serializer[Any]):
    student = serializers.UUIDField()
    full_name = serializers.CharField()
    cells = PerformanceCellSerializer(many=True)


class PerformanceSerializer(serializers.Serializer[Any]):
    first = serializers.DateField()
    last = serializers.DateField()
    courses = PerformanceCourseSerializer(many=True)
    students = PerformanceStudentSerializer(many=True)


class FillRateRowSerializer(serializers.Serializer[Any]):
    teacher = serializers.UUIDField()
    teacher_name = serializers.CharField()
    due = serializers.IntegerField()
    conducted = serializers.IntegerField()
    unfilled = serializers.IntegerField()
    overdue = serializers.IntegerField()
    no_topic = serializers.IntegerField()
    filled_percent = dec(1)


class FillRateSerializer(serializers.Serializer[Any]):
    first = serializers.DateField()
    last = serializers.DateField()
    rows = FillRateRowSerializer(many=True)


class SummaryStudentSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    full_name = serializers.CharField()
    groups = serializers.ListField(child=serializers.CharField())
    parent_name = serializers.CharField(allow_blank=True)
    target = serializers.CharField(allow_blank=True)


class SummarySubjectSerializer(StatsFields):
    subject_name = serializers.CharField()
    teacher_name = serializers.CharField()
    group_name = serializers.CharField()


class SummaryExamSerializer(serializers.Serializer[Any]):
    subject_name = serializers.CharField()
    title = serializers.CharField()
    date = serializers.DateField()
    total = serializers.IntegerField(allow_null=True)
    max_score = serializers.IntegerField()
    percent = dec(1)
    was_absent = serializers.BooleanField()
    target_percent = serializers.IntegerField(allow_null=True)


class StudentSummarySerializer(serializers.Serializer[Any]):
    student = SummaryStudentSerializer()
    year_name = serializers.CharField()
    scale = serializers.ChoiceField(choices=GradeScale.choices)
    first = serializers.DateField()
    last = serializers.DateField()
    subjects = SummarySubjectSerializer(many=True)
    exams = SummaryExamSerializer(many=True)
