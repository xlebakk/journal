"""Mock exam rules. Same access model as the journal: a teacher works with exams of their
courses (and sees only their courses' students), results are editable for the journal's
edit window after the exam date, later — by the administrator with a reason (stage 5)."""

import statistics
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import transaction
from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from apps.academics.models import Course, GroupMembership, members_on
from apps.accounts.models import User
from apps.audit import services as audit
from apps.core.models import CenterSettings
from apps.journal.services import Actor, Forbidden, Rule, actor, today
from apps.schedule.services import VersionConflict

from .models import Exam, ExamResult, ExamSection, ExamSectionScore


def staff_courses(who: Actor) -> QuerySet[Course]:
    qs = Course.objects.all()
    return (
        qs if who.is_admin else qs.filter(Q(teacher=who.user) | Q(assistants=who.user)).distinct()
    )


def exams_for(who: Actor) -> QuerySet[Exam]:
    qs = Exam.objects.select_related("subject")
    if who.is_admin:
        return qs
    return qs.filter(courses__in=staff_courses(who)).distinct()


def get_exam(request: Request, pk: Any) -> tuple[Exam, Actor]:
    who = actor(request)
    return get_object_or_404(exams_for(who), pk=pk), who


def visible_courses(exam: Exam, who: Actor) -> list[Course]:
    courses = exam.courses.select_related("group", "subject", "teacher")
    if not who.is_admin:
        courses = courses.filter(pk__in=staff_courses(who).values("pk"))
    return list(courses.order_by("group__name"))


def students(exam: Exam, who: Actor) -> list[tuple[User, Course]]:
    """Students of the visible courses who were in the group on the exam date."""
    courses = visible_courses(exam, who)
    by_group = {c.group_id: c for c in courses}
    rows = (
        GroupMembership.objects.filter(members_on(exam.date), group_id__in=by_group)
        .select_related("student")
        .order_by("student__last_name", "student__first_name")
    )
    seen: set[Any] = set()
    result = []
    for m in rows:
        if m.student_id not in seen:
            seen.add(m.student_id)
            result.append((m.student, by_group[m.group_id]))
    return result


def window_closes_on(exam: Exam) -> date:
    return exam.date + timedelta(days=CenterSettings.load().edit_window_days)


def editability(exam: Exam, who: Actor) -> tuple[bool, bool, str | None]:
    """(editable, needs_reason, locked)."""
    if exam.date > today():
        return False, False, "future"
    closed = today() > window_closes_on(exam)
    if closed and not who.is_admin:
        return False, False, "window"
    return True, closed, None


def require_writable(exam: Exam, who: Actor, reason: str) -> None:
    _, needs_reason, locked = editability(exam, who)
    if locked == "future":
        raise Rule("exam_in_future")
    if locked == "window":
        raise Forbidden("edit_window_closed")
    if needs_reason and not reason.strip():
        raise Rule("reason_required")


# --- Exams ---------------------------------------------------------------------------------


def _check_courses(who: Actor, courses: list[Course], subject_id: Any) -> None:
    if not courses:
        raise ValidationError({"courses": ["required"]})
    allowed = set(staff_courses(who).values_list("pk", flat=True))
    if any(c.pk not in allowed for c in courses):
        raise ValidationError({"courses": ["not_your_course"]})
    if any(c.subject_id != subject_id for c in courses):
        raise ValidationError({"courses": ["subject_mismatch"]})


def _check_sections(max_score: int, sections: list[dict[str, Any]]) -> None:
    if sections and sum(int(s["max_score"]) for s in sections) != max_score:
        raise ValidationError({"sections": ["sections_sum_mismatch"]})
    names = [s["name"].strip().lower() for s in sections]
    if len(names) != len(set(names)):
        raise ValidationError({"sections": ["duplicate_section"]})


def _snapshot(exam: Exam) -> dict[str, Any]:
    return {
        "title": exam.title,
        "subject": str(exam.subject_id),
        "date": exam.date.isoformat(),
        "max_score": exam.max_score,
        "courses": sorted(str(pk) for pk in exam.courses.values_list("pk", flat=True)),
        "sections": [(s.name, s.max_score) for s in exam.sections.all()],
    }


def create_exam(request: Request, data: dict[str, Any]) -> Exam:
    who = actor(request)
    courses = list(data["courses"])
    _check_courses(who, courses, data["subject"].pk)
    sections = data.get("sections", [])
    _check_sections(data["max_score"], sections)
    with transaction.atomic():
        exam = Exam.objects.create(
            title=data["title"],
            subject=data["subject"],
            date=data["date"],
            max_score=data["max_score"],
            created_by=who.user,
        )
        exam.courses.set(courses)
        for i, section in enumerate(sections):
            ExamSection.objects.create(
                exam=exam, name=section["name"].strip(), max_score=section["max_score"], position=i
            )
        audit.record(request=request, action="exam.create", entity=exam, after=_snapshot(exam))
    return exam


def update_exam(request: Request, pk: Any, data: dict[str, Any]) -> Exam:
    exam, who = get_exam(request, pk)
    with transaction.atomic():
        exam = Exam.objects.select_for_update().get(pk=exam.pk)
        if exam.version != data["version"]:
            raise VersionConflict()
        before = _snapshot(exam)
        has_results = exam.results.exists()
        structural = any(k in data for k in ("max_score", "sections", "subject"))
        if structural and has_results:
            raise Rule("exam_has_results")
        if "courses" in data:
            _check_courses(who, list(data["courses"]), data.get("subject", exam.subject).pk)
            if not who.is_admin:
                # A teacher cannot drop other teachers' courses from a shared exam.
                foreign = exam.courses.exclude(pk__in=staff_courses(who).values("pk"))
                if foreign.exists():
                    raise Forbidden("not_your_exam")
            exam.courses.set(data["courses"])
        for name in ("title", "date", "max_score", "subject"):
            if name in data:
                setattr(exam, name, data[name])
        if "sections" in data:
            _check_sections(exam.max_score, data["sections"])
            exam.sections.all().delete()
            for i, section in enumerate(data["sections"]):
                ExamSection.objects.create(
                    exam=exam,
                    name=section["name"].strip(),
                    max_score=section["max_score"],
                    position=i,
                )
        elif "max_score" in data and exam.sections.exists():
            _check_sections(
                exam.max_score, [dict(x) for x in exam.sections.values("name", "max_score")]
            )
        exam.version += 1
        exam.save()
        audit.record(
            request=request, action="exam.update", entity=exam, before=before, after=_snapshot(exam)
        )
    return exam


def delete_exam(request: Request, pk: Any) -> None:
    exam, who = get_exam(request, pk)
    if exam.results.exists():
        raise Rule("exam_has_results")
    if not who.is_admin and exam.courses.exclude(pk__in=staff_courses(who).values("pk")).exists():
        raise Forbidden("not_your_exam")
    with transaction.atomic():
        before = _snapshot(exam)
        exam_id = exam.pk
        exam.delete()
        audit.record(
            request=request,
            action="exam.delete",
            entity_type="exams.exam",
            entity_id=str(exam_id),
            before=before,
        )


# --- Results -------------------------------------------------------------------------------


def _result_snapshot(result: ExamResult) -> dict[str, Any]:
    return {
        "total": result.total,
        "was_absent": result.was_absent,
        "sections": {str(s.section_id): s.score for s in result.section_scores.all()},
        "comment": result.comment,
    }


def set_result(request: Request, exam_id: Any, student_id: Any, data: dict[str, Any]) -> ExamResult:
    exam, who = get_exam(request, exam_id)
    reason = data.get("reason", "")
    with transaction.atomic():
        exam = Exam.objects.select_for_update().get(pk=exam.pk)
        require_writable(exam, who, reason)
        allowed = {s.pk: s for s, _ in students(exam, who)}
        student = allowed.get(_uuid(student_id))
        if student is None:
            raise Rule("student_not_in_exam")
        sections = {s.pk: s for s in exam.sections.all()}
        absent = bool(data.get("was_absent"))
        scores: dict[Any, int] = {}
        total: int | None = None
        if not absent:
            if sections:
                given = {_uuid(k): v for k, v in (data.get("sections") or {}).items()}
                if set(given) != set(sections):
                    raise ValidationError({"sections": ["all_sections_required"]})
                for sid, score in given.items():
                    if not isinstance(score, int) or not 0 <= score <= sections[sid].max_score:
                        raise ValidationError({"sections": ["score_out_of_range"]})
                    scores[sid] = score
                total = sum(scores.values())
            else:
                total = data.get("total")
                if not isinstance(total, int) or not 0 <= total <= exam.max_score:
                    raise ValidationError({"total": ["score_out_of_range"]})
        result = ExamResult.objects.filter(exam=exam, student=student).first()
        before = _result_snapshot(result) if result else None
        if result is None:
            result = ExamResult(exam=exam, student=student)
        elif data.get("version") != result.version:
            raise VersionConflict()
        else:
            result.version += 1
        result.total = total
        result.was_absent = absent
        result.comment = data.get("comment", result.comment) or ""
        result.entered_by = who.user
        result.save()
        result.section_scores.all().delete()
        ExamSectionScore.objects.bulk_create(
            ExamSectionScore(result=result, section_id=sid, score=score)
            for sid, score in scores.items()
        )
        audit.record(
            request=request,
            action="exam.result_set",
            entity=result,
            before=before,
            after=_result_snapshot(result),
            reason=reason.strip(),
        )
    return result


def clear_result(
    request: Request, exam_id: Any, student_id: Any, version: int, reason: str
) -> None:
    exam, who = get_exam(request, exam_id)
    with transaction.atomic():
        require_writable(exam, who, reason)
        allowed = {s.pk for s, _ in students(exam, who)}
        result = get_object_or_404(ExamResult, exam=exam, student_id=student_id)
        if result.student_id not in allowed:
            raise Rule("student_not_in_exam")
        if result.version != version:
            raise VersionConflict()
        before = _result_snapshot(result)
        result.delete()
        audit.record(
            request=request,
            action="exam.result_clear",
            entity=exam,
            before=before,
            after={"student": str(student_id)},
            reason=reason.strip(),
        )


def _uuid(value: Any) -> Any:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


# --- Statistics ----------------------------------------------------------------------------


def percent(value: int | None, maximum: int) -> Decimal | None:
    if value is None or maximum <= 0:
        return None
    return (Decimal(value) * 100 / Decimal(maximum)).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )


@dataclass
class Summary:
    count: int
    absent: int
    mean: Decimal | None
    median: Decimal | None
    minimum: int | None
    maximum: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "absent": self.absent,
            "mean": self.mean,
            "median": self.median,
            "min": self.minimum,
            "max": self.maximum,
        }


def summarise(totals: list[int], absent: int) -> Summary:
    if not totals:
        return Summary(0, absent, None, None, None, None)
    two = Decimal("0.01")
    mean = (Decimal(sum(totals)) / len(totals)).quantize(two, rounding=ROUND_HALF_UP)
    median = Decimal(str(statistics.median(totals))).quantize(two, rounding=ROUND_HALF_UP)
    return Summary(len(totals), absent, mean, median, min(totals), max(totals))


def distribution(totals: list[int], maximum: int, buckets: int = 10) -> list[dict[str, Any]]:
    """Counts per 10 % band of the maximum: 0–9 %, 10–19 %, … 90–100 %."""
    counts = [0] * buckets
    for total in totals:
        idx = min(buckets - 1, int(total * buckets / maximum)) if maximum else 0
        counts[idx] += 1
    step = 100 // buckets
    return [
        {
            "from_percent": i * step,
            "to_percent": 100 if i == buckets - 1 else (i + 1) * step - 1,
            "count": c,
        }
        for i, c in enumerate(counts)
    ]
