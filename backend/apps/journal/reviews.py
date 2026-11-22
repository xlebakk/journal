"""Teacher reviews once per term (stage 9).

* Written by the course's teacher (not assistants — like setting up mock exams) or the
  administrator; everyone on the course team reads them.
* From the start of the term until `edit_window_days` after its end; later only the
  administrator, with a reason. Every change goes to the audit log.
* Only for students who were in the group at some point of the term.
* An empty text deletes the review.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from apps.academics.models import Course, GroupMembership, Term
from apps.accounts.models import User
from apps.audit import services as audit
from apps.core.models import CenterSettings
from apps.schedule.services import VersionConflict

from .models import TeacherReview
from .services import Actor, Forbidden, Rule, today

MAX_LENGTH = 600


def term_for(course: Course, term_id: Any) -> Term:
    """The requested term of the course's year, or the current one, or the latest started."""
    terms = Term.objects.filter(year=course.group.academic_year)
    if term_id:
        return get_object_or_404(terms, pk=term_id)
    day = today()
    current = terms.filter(starts_on__lte=day, ends_on__gte=day).first()
    started = terms.filter(starts_on__lte=day).order_by("-starts_on").first()
    found = current or started or terms.order_by("starts_on").first()
    if found is None:
        raise Rule("no_terms")
    return found


def can_write(who: Actor, course: Course) -> bool:
    return who.is_admin or course.teacher_id == who.user.pk


@dataclass(frozen=True)
class Editability:
    editable: bool
    needs_reason: bool
    locked: str | None  # "future" | "window" | "not_course_teacher"
    closes_on: date


def editability(who: Actor, course: Course, term: Term) -> Editability:
    closes = term.ends_on + timedelta(days=CenterSettings.load().edit_window_days)
    if not can_write(who, course):
        return Editability(False, False, "not_course_teacher", closes)
    if today() < term.starts_on:
        return Editability(False, False, "future", closes)
    closed = today() > closes
    if closed and not who.is_admin:
        return Editability(False, False, "window", closes)
    return Editability(True, closed, None, closes)


def students(course: Course, term: Term) -> list[User]:
    """Everyone who was in the group on at least one day of the term."""
    memberships = (
        GroupMembership.objects.filter(group_id=course.group_id, joined_on__lte=term.ends_on)
        .filter(Q(left_on__isnull=True) | Q(left_on__gte=term.starts_on))
        .select_related("student")
        .order_by("student__last_name", "student__first_name")
    )
    seen: dict[Any, User] = {}
    for m in memberships:
        seen.setdefault(m.student_id, m.student)
    return list(seen.values())


def _snapshot(review: TeacherReview | None) -> dict[str, Any] | None:
    if review is None:
        return None
    return {"text": review.text, "term": str(review.term_id), "student": str(review.student_id)}


def set_review(
    request: Request,
    who: Actor,
    course: Course,
    term: Term,
    student_id: Any,
    text: str,
    version: int | None,
    reason: str,
) -> TeacherReview | None:
    state = editability(who, course, term)
    if state.locked == "not_course_teacher":
        raise Forbidden("not_course_teacher")
    if state.locked == "future":
        raise Rule("term_not_started")
    if state.locked == "window":
        raise Forbidden("edit_window_closed")
    if state.needs_reason and not reason.strip():
        raise Rule("reason_required")
    text = text.strip()
    if len(text) > MAX_LENGTH:
        raise ValidationError({"text": ["too_long"]})
    student = next((s for s in students(course, term) if str(s.pk) == str(student_id)), None)
    if student is None:
        raise Rule("student_not_in_group")
    with transaction.atomic():
        review = (
            TeacherReview.objects.select_for_update()
            .filter(course=course, student=student, term=term)
            .first()
        )
        if review is not None and review.version != version:
            raise VersionConflict()
        before = _snapshot(review)
        if not text:
            if review is None:
                return None
            review.delete()
            audit.record(
                request=request,
                action="review.delete",
                entity_type="journal.teacherreview",
                entity_id=str(review.pk),
                before=before,
                reason=reason.strip(),
            )
            return None
        if review is None:
            review = TeacherReview.objects.create(
                course=course, student=student, term=term, text=text, author=who.user
            )
            action = "review.create"
        else:
            review.text = text
            review.author = who.user
            review.version += 1
            review.save()
            action = "review.update"
        audit.record(
            request=request,
            action=action,
            entity=review,
            before=before,
            after=_snapshot(review),
            reason=reason.strip(),
        )
    return review
