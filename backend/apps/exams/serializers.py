from typing import Any

from rest_framework import serializers

from apps.academics.models import Course, Subject

from .models import Exam, ExamSection


class SectionSerializer(serializers.ModelSerializer[ExamSection]):
    class Meta:
        model = ExamSection
        fields = ("id", "name", "max_score")
        read_only_fields = ("id",)


class SectionWriteSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=120)
    max_score = serializers.IntegerField(min_value=1, max_value=1000)


class ExamCourseSerializer(serializers.ModelSerializer[Course]):
    group_name = serializers.CharField(source="group.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.short_name", read_only=True)

    class Meta:
        model = Course
        fields = ("id", "group_name", "teacher_name")
        read_only_fields = fields


class ExamSerializer(serializers.ModelSerializer[Exam]):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    courses = ExamCourseSerializer(many=True, read_only=True)
    sections = SectionSerializer(many=True, read_only=True)
    results_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Exam
        fields = (
            "id",
            "title",
            "subject",
            "subject_name",
            "date",
            "max_score",
            "courses",
            "sections",
            "results_count",
            "version",
        )
        read_only_fields = fields


class ExamWriteSerializer(serializers.Serializer[Any]):
    title = serializers.CharField(max_length=200)
    subject = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.all())
    date = serializers.DateField()
    max_score = serializers.IntegerField(min_value=1, max_value=1000)
    courses = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.select_related("group"), many=True
    )
    sections = SectionWriteSerializer(many=True, required=False)


class ExamUpdateSerializer(ExamWriteSerializer):
    version = serializers.IntegerField(min_value=1)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, partial=True, **kwargs)


class ResultWriteSerializer(serializers.Serializer[Any]):
    total = serializers.IntegerField(required=False, allow_null=True)
    sections = serializers.DictField(child=serializers.IntegerField(), required=False)
    was_absent = serializers.BooleanField(default=False)
    comment = serializers.CharField(max_length=300, required=False, allow_blank=True)
    version = serializers.IntegerField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class ClearSerializer(serializers.Serializer[Any]):
    version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class ResultRowSerializer(serializers.Serializer[Any]):
    student = serializers.UUIDField()
    student_name = serializers.CharField()
    login = serializers.CharField()
    group_name = serializers.CharField()
    result = serializers.UUIDField(allow_null=True)
    total = serializers.IntegerField(allow_null=True)
    percent = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)
    was_absent = serializers.BooleanField()
    comment = serializers.CharField(allow_blank=True)
    sections = serializers.DictField(child=serializers.IntegerField())
    version = serializers.IntegerField(allow_null=True)


class ResultsTableSerializer(serializers.Serializer[Any]):
    exam = ExamSerializer()
    editable = serializers.BooleanField()
    needs_reason = serializers.BooleanField()
    locked = serializers.CharField(allow_null=True)
    window_closes_on = serializers.DateField()
    rows = ResultRowSerializer(many=True)


class SummarySerializer(serializers.Serializer[Any]):
    count = serializers.IntegerField()
    absent = serializers.IntegerField()
    mean = serializers.DecimalField(max_digits=7, decimal_places=2, allow_null=True)
    median = serializers.DecimalField(max_digits=7, decimal_places=2, allow_null=True)
    min = serializers.IntegerField(allow_null=True)
    max = serializers.IntegerField(allow_null=True)


class BucketSerializer(serializers.Serializer[Any]):
    from_percent = serializers.IntegerField()
    to_percent = serializers.IntegerField()
    count = serializers.IntegerField()


class ExamGroupSummarySerializer(SummarySerializer):
    group_name = serializers.CharField()
    mean_percent = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)


class SectionStatSerializer(serializers.Serializer[Any]):
    name = serializers.CharField()
    max_score = serializers.IntegerField()
    mean = serializers.DecimalField(max_digits=7, decimal_places=2, allow_null=True)
    mean_percent = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)


class ExamStatsSerializer(serializers.Serializer[Any]):
    exam = ExamSerializer()
    summary = SummarySerializer()
    mean_percent = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)
    distribution = BucketSerializer(many=True)
    groups = ExamGroupSummarySerializer(many=True)
    sections = SectionStatSerializer(many=True)


class DynamicsPointSerializer(serializers.Serializer[Any]):
    exam = serializers.UUIDField()
    title = serializers.CharField()
    date = serializers.DateField()
    count = serializers.IntegerField()
    mean_percent = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)


class ExamImportRowSerializer(serializers.Serializer[Any]):
    line = serializers.IntegerField()
    student_name = serializers.CharField(allow_blank=True)
    login = serializers.CharField(allow_blank=True)
    total = serializers.IntegerField(allow_null=True)
    was_absent = serializers.BooleanField()
    issues = serializers.ListField(child=serializers.CharField())


class ImportResultSerializer(serializers.Serializer[Any]):
    applied = serializers.BooleanField()
    rows = ExamImportRowSerializer(many=True)


class StudentExamSectionSerializer(serializers.Serializer[Any]):
    name = serializers.CharField()
    score = serializers.IntegerField()
    max_score = serializers.IntegerField()
    percent = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)


class StudentExamSerializer(serializers.Serializer[Any]):
    exam = serializers.UUIDField()
    title = serializers.CharField()
    date = serializers.DateField()
    total = serializers.IntegerField(allow_null=True)
    max_score = serializers.IntegerField()
    percent = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)
    change = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)
    was_absent = serializers.BooleanField()
    sections = StudentExamSectionSerializer(many=True)


class StudentSubjectExamsSerializer(serializers.Serializer[Any]):
    subject = serializers.UUIDField()
    subject_name = serializers.CharField()
    target_percent = serializers.IntegerField(allow_null=True)
    exams = StudentExamSerializer(many=True)


class TargetSerializer(serializers.Serializer[Any]):
    subject = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.all())
    percent = serializers.IntegerField(min_value=1, max_value=100)
