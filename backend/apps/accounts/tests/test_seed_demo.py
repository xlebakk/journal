from datetime import date
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
    # The super admin and the head of studies with three sections (stage 16).
    assert User.objects.with_role(Role.ADMIN).count() == 2
    assert User.objects.filter(is_superadmin=True).count() == 1
    head = User.objects.with_role(Role.ADMIN).get(is_superadmin=False)
    assert sorted(head.admin_sections) == ["journal", "reports", "schedule"]
    assert User.objects.with_role(Role.TEACHER).count() == 6
    assert User.objects.with_role(Role.STUDENT).count() == 60
    assert Group.objects.count() == 4
    assert Course.objects.count() == 17
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
    # Stage 17: every group studies every day of its week (weekdays or the weekend).
    from apps.schedule.models import ScheduleSlot

    for group in Group.objects.all():
        days = set(
            ScheduleSlot.objects.filter(course__group=group).values_list("weekday", flat=True)
        )
        assert days in ({1, 2, 3, 4, 5}, {6, 7}), group.name
    # ...and every teacher teaches every weekday.
    for teacher in User.objects.with_role(Role.TEACHER):
        days = set(
            ScheduleSlot.objects.filter(course__teacher=teacher).values_list("weekday", flat=True)
        )
        assert {1, 2, 3, 4, 5} <= days, teacher.full_name
    from apps.schedule.models import ScheduleRequest

    assert ScheduleRequest.objects.filter(status="pending").exists()
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
    from apps.journal.models import TeacherReview

    assert TeacherReview.objects.filter(term__name="Модуль 1").exists()  # finished before today
    from apps.payments.models import Charge, Payment
    from apps.payments.services import balances

    assert Charge.objects.filter(month=date(2026, 9, 1)).exists()
    students = list(User.objects.with_role(Role.STUDENT).values_list("pk", flat=True))
    debts = [b.debt for b in balances(students).values()]
    assert any(d > 0 for d in debts)  # debtors to show
    assert all(d >= 0 for d in debts)  # nobody paid more than charged
    assert Payment.objects.exists()
    from apps.accounts.models import ParentLink

    assert User.objects.with_role(Role.PARENT).count() == 3
    assert ParentLink.objects.count() == 4  # one parent has two children
    text = out.getvalue()
    admin = User.objects.get(is_superadmin=True)
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


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_seed_demo_can_give_everyone_one_password() -> None:
    call_command("seed_demo", password="демо пароль 2026", stdout=StringIO())
    users = list(User.objects.all())
    assert users
    assert all(u.check_password("демо пароль 2026") for u in users[:5] + users[-5:])
