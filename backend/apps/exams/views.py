"""Mock exams API for staff and students."""

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role, User
from apps.accounts.permissions import (
    STUDENT_PAGES,
    IsAdmin,
    IsTeacher,
    subject_student,
)
from apps.audit import services as audit
from apps.core.files import read_table
from apps.core.params import uuid_param
from apps.journal.services import actor

from . import serializers as s
from . import services
from .models import Exam, ExamResult, StudentTarget

STAFF = (IsAdmin | IsTeacher,)


def _annotated(exam: Exam) -> Exam:
    return (
        Exam.objects.select_related("subject")
        .prefetch_related("courses__group", "courses__teacher", "sections")
        .annotate(results_count=Count("results"))
        .get(pk=exam.pk)
    )


def _exam_data(exam: Exam) -> dict[str, Any]:
    return dict(s.ExamSerializer(_annotated(exam)).data)


class ExamListView(APIView):
    permission_classes = STAFF

    @extend_schema(
        parameters=[OpenApiParameter("subject", str)], responses=s.ExamSerializer(many=True)
    )
    def get(self, request: Request) -> Response:
        qs = (
            services.exams_for(actor(request))
            .prefetch_related("courses__group", "courses__teacher", "sections")
            .annotate(results_count=Count("results", distinct=True))
        )
        if subject := uuid_param(request, "subject"):
            qs = qs.filter(subject__pk=subject)
        return Response(s.ExamSerializer(qs[:200], many=True).data)

    @extend_schema(request=s.ExamWriteSerializer, responses={201: s.ExamSerializer})
    def post(self, request: Request) -> Response:
        form = s.ExamWriteSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        exam = services.create_exam(request, form.validated_data)
        return Response(_exam_data(exam), status=201)


class ExamDetailView(APIView):
    permission_classes = STAFF

    @extend_schema(responses=s.ExamSerializer)
    def get(self, request: Request, pk: str) -> Response:
        exam, _ = services.get_exam(request, pk)
        return Response(_exam_data(exam))

    @extend_schema(request=s.ExamUpdateSerializer, responses=s.ExamSerializer)
    def patch(self, request: Request, pk: str) -> Response:
        form = s.ExamUpdateSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        exam = services.update_exam(request, pk, form.validated_data)
        return Response(_exam_data(exam))

    @extend_schema(responses={204: None})
    def delete(self, request: Request, pk: str) -> Response:
        services.delete_exam(request, pk)
        return Response(status=204)


def _rows(exam: Exam, who: Any) -> list[dict[str, Any]]:
    people = services.students(exam, who)
    results = {
        r.student_id: r
        for r in ExamResult.objects.filter(
            exam=exam, student__in=[p for p, _ in people]
        ).prefetch_related("section_scores")
    }
    rows = []
    for student, course in people:
        result = results.get(student.pk)
        rows.append(
            {
                "student": student.pk,
                "student_name": student.full_name,
                "login": student.login,
                "group_name": course.group.name,
                "result": result.pk if result else None,
                "total": result.total if result else None,
                "percent": services.percent(result.total, exam.max_score) if result else None,
                "was_absent": result.was_absent if result else False,
                "comment": result.comment if result else "",
                "sections": {str(x.section_id): x.score for x in result.section_scores.all()}
                if result
                else {},
                "version": result.version if result else None,
            }
        )
    return rows


class ExamResultsView(APIView):
    """The results table: students of the visible courses on the exam date."""

    permission_classes = STAFF

    @extend_schema(responses=s.ResultsTableSerializer)
    def get(self, request: Request, pk: str) -> Response:
        exam, who = services.get_exam(request, pk)
        editable, needs_reason, locked = services.editability(exam, who)
        data = {
            "exam": _annotated(exam),
            "editable": editable,
            "needs_reason": needs_reason,
            "locked": locked,
            "window_closes_on": services.window_closes_on(exam),
            "rows": _rows(exam, who),
        }
        return Response(s.ResultsTableSerializer(data).data)


class ExamResultView(APIView):
    permission_classes = STAFF

    @extend_schema(request=s.ResultWriteSerializer, responses=s.ResultRowSerializer)
    def put(self, request: Request, pk: str, student_id: str) -> Response:
        form = s.ResultWriteSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        services.set_result(request, pk, student_id, form.validated_data)
        exam, who = services.get_exam(request, pk)
        row = next(r for r in _rows(exam, who) if str(r["student"]) == str(student_id))
        return Response(s.ResultRowSerializer(row).data)


class ExamResultClearView(APIView):
    permission_classes = STAFF

    @extend_schema(request=s.ClearSerializer, responses={204: None})
    def post(self, request: Request, pk: str, student_id: str) -> Response:
        form = s.ClearSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        services.clear_result(
            request, pk, student_id, form.validated_data["version"], form.validated_data["reason"]
        )
        return Response(status=204)


ABSENT_MARKS = {"н", "n", "отс", "отсутствовал", "absent"}
IMPORT_FORM = {
    "type": "object",
    "properties": {
        "file": {"type": "string", "format": "binary"},
        "apply": {"type": "boolean"},
        "reason": {"type": "string"},
    },
}


class ExamImportView(APIView):
    """Results from an XLSX/CSV: «Логин» (or «ФИО»), «Балл» or one column per section; «н» —
    absent. Without `apply=true` only the preview with errors per line is returned; with it,
    all rows are written in one transaction, and only if there are no errors."""

    permission_classes = STAFF
    parser_classes = (MultiPartParser,)
    throttle_scope = "import"

    @extend_schema(request={"multipart/form-data": IMPORT_FORM}, responses=s.ImportResultSerializer)
    def post(self, request: Request, pk: str) -> Response:
        exam, who = services.get_exam(request, pk)
        form: Any = request.data
        reason = str(form.get("reason", ""))
        services.require_writable(exam, who, reason)
        table = read_table(request.FILES.get("file"))
        people = {p.login: p for p, _ in services.students(exam, who)}
        by_name = {p.full_name.lower(): p for p in people.values()}
        sections = list(exam.sections.all())
        rows: list[dict[str, Any]] = []
        writes: list[tuple[User, dict[str, Any]]] = []
        for line, row in enumerate(table, start=2):
            errors: list[str] = []
            login = row.get("логин", "").lower()
            name = row.get("фио", "")
            student = people.get(login) or by_name.get(name.lower())
            if student is None:
                errors.append("student_not_in_exam")
            raw_total = row.get("балл", "")
            absent = raw_total.lower() in ABSENT_MARKS
            payload: dict[str, Any] = {"was_absent": absent}
            total: int | None = None
            if not absent:
                if sections:
                    scores = {}
                    for section in sections:
                        value = row.get(section.name.lower(), "")
                        if not value.isdigit() or int(value) > section.max_score:
                            errors.append(f"bad_section:{section.name}")
                        else:
                            scores[str(section.pk)] = int(value)
                    payload["sections"] = scores
                    total = sum(scores.values()) if len(scores) == len(sections) else None
                elif not raw_total.isdigit() or int(raw_total) > exam.max_score:
                    errors.append("score_out_of_range")
                else:
                    total = int(raw_total)
                    payload["total"] = total
            rows.append(
                {
                    "line": line,
                    "student_name": student.full_name if student else name,
                    "login": student.login if student else login,
                    "total": total,
                    "was_absent": absent,
                    "issues": errors,
                }
            )
            if student is not None and not errors:
                writes.append((student, payload))
        apply = str(form.get("apply", "")).lower() == "true"
        if apply and all(not r["issues"] for r in rows):
            existing = {r.student_id: r.version for r in ExamResult.objects.filter(exam=exam)}
            with transaction.atomic():
                for student, payload in writes:
                    payload["version"] = existing.get(student.pk)
                    payload["reason"] = reason
                    services.set_result(request, exam.pk, student.pk, payload)
            return Response(s.ImportResultSerializer({"applied": True, "rows": rows}).data)
        return Response(s.ImportResultSerializer({"applied": False, "rows": rows}).data)


class ExamStatsView(APIView):
    """Mean, median, distribution, groups compared, sections."""

    permission_classes = STAFF

    @extend_schema(responses=s.ExamStatsSerializer)
    def get(self, request: Request, pk: str) -> Response:
        exam, who = services.get_exam(request, pk)
        rows = _rows(exam, who)
        present = [r for r in rows if r["result"] and not r["was_absent"]]
        totals = [int(r["total"]) for r in present]
        absent = sum(1 for r in rows if r["was_absent"])
        summary = services.summarise(totals, absent)
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in rows:
            groups[r["group_name"]].append(r)
        group_rows = []
        for name, members in sorted(groups.items()):
            group_totals = [int(r["total"]) for r in members if r["result"] and not r["was_absent"]]
            g = services.summarise(group_totals, sum(1 for r in members if r["was_absent"]))
            group_rows.append(
                {
                    **g.as_dict(),
                    "group_name": name,
                    "mean_percent": _mean_percent(g.mean, exam.max_score),
                }
            )
        section_rows = []
        for section in exam.sections.all():
            values = [r["sections"].get(str(section.pk)) for r in present]
            scores = [v for v in values if v is not None]
            mean = (
                (Decimal(sum(scores)) / len(scores)).quantize(Decimal("0.01")) if scores else None
            )
            section_rows.append(
                {
                    "name": section.name,
                    "max_score": section.max_score,
                    "mean": mean,
                    "mean_percent": _mean_percent(mean, section.max_score),
                }
            )
        data = {
            "exam": _annotated(exam),
            "summary": summary.as_dict(),
            "mean_percent": _mean_percent(summary.mean, exam.max_score),
            "distribution": services.distribution(totals, exam.max_score),
            "groups": group_rows,
            "sections": section_rows,
        }
        return Response(s.ExamStatsSerializer(data).data)


def _mean_percent(mean: Decimal | None, maximum: int) -> Decimal | None:
    if mean is None or maximum <= 0:
        return None
    return (mean * 100 / maximum).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


class ExamDynamicsView(APIView):
    """Mean % per exam of a subject over time: the center's dynamics."""

    permission_classes = STAFF

    @extend_schema(
        parameters=[OpenApiParameter("subject", str)],
        responses=s.DynamicsPointSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        who = actor(request)
        qs = services.exams_for(who).order_by("date")
        if subject := uuid_param(request, "subject"):
            qs = qs.filter(subject__pk=subject)
        points = []
        for exam in qs[:100]:
            rows = _rows(exam, who)
            totals = [int(r["total"]) for r in rows if r["result"] and not r["was_absent"]]
            summary = services.summarise(totals, 0)
            points.append(
                {
                    "exam": exam.pk,
                    "title": exam.title,
                    "date": exam.date,
                    "count": summary.count,
                    "mean_percent": _mean_percent(summary.mean, exam.max_score),
                }
            )
        return Response(s.DynamicsPointSerializer(points, many=True).data)


class StudentExamsView(APIView):
    """«Пробные тесты» of a student: per subject, own results only, target in %."""

    permission_classes = STUDENT_PAGES

    @extend_schema(responses=s.StudentSubjectExamsSerializer(many=True))
    def get(self, request: Request) -> Response:
        me = subject_student(request)
        results = (
            ExamResult.objects.filter(student=me)
            .select_related("exam__subject")
            .prefetch_related("section_scores__section")
            .order_by("exam__date", "exam__title")
        )
        targets = dict(
            StudentTarget.objects.filter(student=me).values_list("subject_id", "percent")
        )
        subjects: dict[Any, dict[str, Any]] = {}
        for result in results:
            exam = result.exam
            row = subjects.setdefault(
                exam.subject_id,
                {
                    "subject": exam.subject_id,
                    "subject_name": exam.subject.name,
                    "target_percent": targets.get(exam.subject_id),
                    "exams": [],
                },
            )
            pct = services.percent(result.total, exam.max_score)
            previous = next(
                (e["percent"] for e in reversed(row["exams"]) if e["percent"] is not None), None
            )
            scores = sorted(result.section_scores.all(), key=lambda x: x.section.position)
            row["exams"].append(
                {
                    "exam": exam.pk,
                    "title": exam.title,
                    "date": exam.date,
                    "total": result.total,
                    "max_score": exam.max_score,
                    "percent": pct,
                    "change": pct - previous if pct is not None and previous is not None else None,
                    "was_absent": result.was_absent,
                    "sections": [
                        {
                            "name": x.section.name,
                            "score": x.score,
                            "max_score": x.section.max_score,
                            "percent": services.percent(x.score, x.section.max_score),
                        }
                        for x in scores
                    ],
                }
            )
        ordered = sorted(subjects.values(), key=lambda r: r["subject_name"])
        return Response(s.StudentSubjectExamsSerializer(ordered, many=True).data)


class StudentTargetsView(APIView):
    """The administrator sets a student's goals per subject, in % (decision of stage 5)."""

    permission_classes = (IsAdmin,)

    def _student(self, pk: str) -> User:
        return get_object_or_404(User.objects.with_role(Role.STUDENT), pk=pk)

    @extend_schema(responses=s.TargetSerializer(many=True))
    def get(self, request: Request, pk: str) -> Response:
        student = self._student(pk)
        rows = StudentTarget.objects.filter(student=student).order_by("subject__name")
        return Response([{"subject": str(t.subject_id), "percent": t.percent} for t in rows])

    @extend_schema(request=s.TargetSerializer(many=True), responses=s.TargetSerializer(many=True))
    def put(self, request: Request, pk: str) -> Response:
        student = self._student(pk)
        form = s.TargetSerializer(data=request.data, many=True)
        form.is_valid(raise_exception=True)
        with transaction.atomic():
            before = {
                str(t.subject_id): t.percent for t in StudentTarget.objects.filter(student=student)
            }
            StudentTarget.objects.filter(student=student).delete()
            for row in form.validated_data:
                StudentTarget.objects.create(
                    student=student, subject=row["subject"], percent=row["percent"]
                )
            after = {str(r["subject"].pk): r["percent"] for r in form.validated_data}
            audit.record(
                request=request,
                action="user.targets_update",
                entity=student,
                before=before,
                after=after,
            )
        return self.get(request, pk)
