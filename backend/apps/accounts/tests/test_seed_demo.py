from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.test import override_settings

from apps.academics.models import Course, Group
from apps.accounts.models import Role, User
from apps.schedule.models import Lesson


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_seed_demo_creates_people_and_prints_passwords() -> None:
    out = StringIO()
    call_command("seed_demo", stdout=out)
    assert User.objects.with_role(Role.ADMIN).count() == 1
    assert User.objects.with_role(Role.TEACHER).count() == 6
    assert User.objects.with_role(Role.STUDENT).count() == 60
    assert Group.objects.count() == 4
    assert Course.objects.count() == 11
    assert Lesson.objects.count() > 100
    # The demo template is conflict-free: no teacher, room or group is double-booked.
    lessons = list(Lesson.objects.exclude(status="cancelled").select_related("course"))
    for a in lessons:
        for b in lessons:
            if (
                a.pk < b.pk
                and a.date == b.date
                and a.start_time < b.end_time
                and b.start_time < a.end_time
            ):
                assert a.teacher_id != b.teacher_id
                assert a.room_id is None or a.room_id != b.room_id
                assert a.course.group_id != b.course.group_id
    # Stage 3: past lessons are conducted with full attendance, a few are left unfilled.
    from apps.journal.models import Attendance, Grade
    from apps.journal.services import members

    conducted = list(Lesson.objects.filter(status="conducted"))
    assert conducted
    assert Grade.objects.exists()
    for lesson in conducted[:20]:
        marked = set(Attendance.objects.filter(lesson=lesson).values_list("student_id", flat=True))
        assert {s.pk for s in members(lesson)} <= marked
        assert lesson.topic
    # Stage 5: exams with results (sections add up), goals, announcements.
    from apps.announcements.models import Announcement
    from apps.exams.models import Exam, ExamResult, StudentTarget

    assert Exam.objects.count() == 6
    for result in ExamResult.objects.filter(was_absent=False).prefetch_related("section_scores"):
        scores = [s.score for s in result.section_scores.all()]
        assert result.total is not None
        assert result.total <= result.exam.max_score
        assert not scores or sum(scores) == result.total
    assert StudentTarget.objects.exists()
    assert Announcement.objects.live().count() == 4
    text = out.getvalue()
    admin = User.objects.with_role(Role.ADMIN).get()
    assert admin.login in text
    assert admin.totp_enabled is False  # set up on first login
    with pytest.raises(CommandError):
        call_command("seed_demo", stdout=StringIO())  # database is no longer empty


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_seed_demo_refuses_outside_development() -> None:
    with pytest.raises(CommandError, match="outside development"):
        call_command("seed_demo", stdout=StringIO())
    assert not User.objects.exists()
