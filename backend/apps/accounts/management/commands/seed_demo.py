"""Demo data.

Stage 1: people. Stage 2: year and terms, subjects, rooms, 4 groups with courses, a week
template without conflicts and 8 weeks of lessons (4 back, 4 ahead) with a few exceptions.
Stage 3: past lessons are conducted with topics, homework, attendance and grades; a couple
of recent lessons are left unfilled and two students need attention.
Stage 5: mock exams (with and without sections, an upcoming one), goals of students per
subject in %, announcements for everyone, a role and a group.
Stage 9: teachers' reviews for the last finished term (a few students per course).
Stage 12: monthly prices of groups, two discounts, charges since September and payments;
every fourth student owes for the current month, one owes for two months.
Stage 14: three parents — one of them with two children.
Stage 16: the super admin and an ordinary administrator (head of studies) with three sections.
Stage 17: a full week for every group (two or three pairs a day), 17 courses, varied homework;
--password gives every demo user one password.
"""

import os
import random
from datetime import date, time, timedelta
from typing import Any, ClassVar

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.academics.models import (
    AcademicYear,
    Course,
    Group,
    GroupMembership,
    Holiday,
    LessonType,
    Room,
    Subject,
    Term,
    WorkType,
)
from apps.accounts import credentials
from apps.accounts.models import (
    AdminSection,
    ParentLink,
    Role,
    StudentProfile,
    TeacherProfile,
    User,
)
from apps.announcements.models import Announcement, Audience
from apps.exams.models import Exam, ExamResult, ExamSection, ExamSectionScore, StudentTarget
from apps.journal.models import Attendance, AttendanceStatus, Grade, TeacherReview
from apps.payments.models import Charge, GroupFee, Payment, PaymentMethod, StudentDiscount
from apps.payments.services import discounted, month_end, month_start
from apps.schedule import services
from apps.schedule.models import Lesson, LessonStatus, ScheduleRequest, ScheduleSlot

LAST_NAMES = [
    ("Алиев", "Алиева"), ("Каримов", "Каримова"), ("Юсупов", "Юсупова"),
    ("Рахимов", "Рахимова"), ("Ахмедов", "Ахмедова"), ("Исмаилов", "Исмаилова"),
    ("Турсунов", "Турсунова"), ("Хасанов", "Хасанова"), ("Назаров", "Назарова"),
    ("Мирзаев", "Мирзаева"), ("Ким", "Ким"), ("Пак", "Пак"), ("Иванов", "Иванова"),
    ("Абдуллаев", "Абдуллаева"), ("Содиков", "Содикова"), ("Шарипов", "Шарипова"),
]  # fmt: skip
MALE = ["Фарход", "Тимур", "Санжар", "Азиз", "Бобур", "Жасур", "Сергей", "Рустам", "Дилшод"]
FEMALE = ["Мадина", "Дилноза", "Нигора", "Малика", "Севара", "Анна", "Камила", "Зарина"]
SCHOOLS = ["Школа № 110", "Лицей при ТГТУ", "Школа № 64", "Президентская школа", "Школа № 21"]
TARGETS = ["ТУИТ, программная инженерия", "НУУз, математика", "ТашГМУ, лечебное дело",
           "Вестминстер, экономика", "Инха, компьютерные науки"]  # fmt: skip

SUBJECTS = [
    ("Математика", "Мат"),
    ("Физика", "Физ"),
    ("Английский язык", "Англ"),
    ("Русский язык", "Рус"),
    ("Химия", "Хим"),
    ("Биология", "Био"),
]
ROOMS = [("101", 16), ("102", 16), ("201", 24), ("202", 12), ("Актовый зал", 60)]
# Teacher index → subjects they teach.
TEACHER_SUBJECTS = [["Мат"], ["Физ"], ["Англ"], ["Рус"], ["Хим"], ["Био"]]
Slot = tuple[int, time, time, str]
T = time
# Pairs of the day: morning A 09:00–10:30, B 10:45–12:15, C 12:30–14:00; evening A 16:00–17:30,
# B 17:45–19:15; weekend from 10:00. Every group studies every day of its week, and every teacher
# teaches every weekday (found by a small search: 35 pairs a week, 5–7 per teacher).
MA, MB, MC = (T(9), T(10, 30)), (T(10, 45), T(12, 15)), (T(12, 30), T(14))
EA, EB = (T(16), T(17, 30)), (T(17, 45), T(19, 15))
W1, W2, W3 = (T(10), T(11, 30)), (T(11, 45), T(13, 15)), (T(13, 30), T(15))


def slots(room: str, *pairs: tuple[int, tuple[time, time]]) -> list[Slot]:
    return [(day, begins, ends, room) for day, (begins, ends) in pairs]


# group → (level, [(subject, teacher index, [slots])]); the test checks it is conflict-free.
GROUPS: dict[str, tuple[str, list[tuple[str, int, list[Slot]]]]] = {
    "11-М вечерняя": ("11 класс", [
        ("Мат", 0, slots("101", (2, EA), (3, EA), (4, EA))),
        ("Физ", 1, slots("101", (1, EA), (3, EB), (5, EB))),
        ("Англ", 2, slots("101", (1, EB), (2, EB))),
        ("Хим", 4, slots("101", (4, EB), (5, EA))),
    ]),
    "11-Б утренняя": ("11 класс", [
        ("Био", 5, slots("201", (1, MC), (4, MC), (5, MA))),
        ("Рус", 3, slots("201", (1, MB), (2, MC), (4, MA))),
        ("Хим", 4, slots("201", (1, MA), (2, MB), (3, MC))),
        ("Мат", 0, slots("201", (3, MB), (5, MC))),
        ("Англ", 2, slots("201", (3, MA), (5, MB))),
        ("Физ", 1, slots("201", (2, MA), (4, MB))),
    ]),
    "10-М выходного дня": ("10 класс", [
        ("Мат", 0, slots("201", (6, W1), (7, W2))),
        ("Англ", 2, slots("201", (6, W2), (7, W1))),
        ("Физ", 1, slots("201", (6, W3))),
    ]),
    "11-Г вечерняя": ("11 класс", [
        ("Рус", 3, slots("102", (3, EA), (4, EB), (5, EB))),
        ("Англ", 2, slots("102", (1, EA), (4, EA), (5, EA))),
        ("Мат", 0, slots("102", (1, EB), (2, EB))),
        ("Био", 5, slots("102", (2, EA), (3, EB))),
    ]),
}  # fmt: skip


class Command(BaseCommand):
    help = "Creates demo data and prints logins and passwords. Never in production."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--seed", type=int, default=2026, help="random seed for names")
        parser.add_argument(
            "--password",
            default="",
            help="one password for every demo user (handy for a demo); random ones by default",
        )

    def handle(self, *args: Any, seed: int, password: str, **options: Any) -> None:
        module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
        if not settings.DEBUG or module.endswith(".prod"):
            raise CommandError("seed_demo refuses to run outside development (DEBUG=False).")
        if User.objects.exists():
            raise CommandError("The database already has users; seed_demo only fills an empty one.")

        # Demo names only, not security.
        self.rng = random.Random(seed)  # noqa: S311  # nosec B311
        self.password = password
        self.rows: list[tuple[str, str, str, str]] = []
        with transaction.atomic():
            teachers, students = self._people()
            self._structure(teachers, students)
        self._print()

    # --- People ----------------------------------------------------------------------------

    def _person(self, female: bool) -> tuple[str, str]:
        last = self.rng.choice(LAST_NAMES)[1 if female else 0]
        return last, self.rng.choice(FEMALE if female else MALE)

    def _make(
        self, roles: list[str], last: str, first: str, sections: list[str] | None = None
    ) -> User:
        password = self.password or credentials.generate_temporary_password()
        user = User.objects.create_user(
            login=credentials.generate_login(last, first),
            password=password,
            last_name=last,
            first_name=first,
            roles=roles,
            # An administrator with sections is an ordinary one; without them — the super admin.
            is_superadmin=Role.ADMIN in roles and sections is None,
            admin_sections=sections or [],
            # Demo convenience: skip the forced change; 2FA is each user's choice.
            must_change_password=False,
        )
        self.rows.append((", ".join(roles), user.full_name, user.login, password))
        return user

    def _people(self) -> tuple[list[User], list[User]]:
        self.admin = self._make([Role.ADMIN], "Администратор", "Демо")
        # Stage 16: an ordinary administrator — the head of studies with three sections.
        self._make(
            [Role.ADMIN],
            "Завуч",
            "Демо",
            sections=[AdminSection.SCHEDULE, AdminSection.JOURNAL, AdminSection.REPORTS],
        )
        teachers = []
        for i in range(6):
            user = self._make([Role.TEACHER], *self._person(female=i % 2 == 1))
            TeacherProfile.objects.create(user=user, phone=f"+998 90 100 00 0{i}")
            teachers.append(user)
        students = []
        for i in range(60):
            user = self._make([Role.STUDENT], *self._person(female=i % 2 == 1))
            StudentProfile.objects.create(
                user=user,
                school=self.rng.choice(SCHOOLS),
                school_grade=self.rng.choice([9, 10, 11]),
                target=self.rng.choice(TARGETS),
                target_score=self.rng.choice([150, 170, 180, 190]),
                parent_name=f"{user.last_name} (родитель)",
                parent_phone=f"+998 91 200 {i:02d} {i:02d}",
            )
            students.append(user)
        return teachers, students

    # --- Structure and schedule ------------------------------------------------------------

    def _structure(self, teachers: list[User], students: list[User]) -> None:
        today = services.today()
        year = AcademicYear.objects.create(
            name="2026/2027", starts_on=date(2026, 9, 1), ends_on=date(2027, 6, 30), is_current=True
        )
        for name, starts, ends in [
            ("Модуль 1", date(2026, 9, 1), date(2026, 10, 31)),
            ("Модуль 2", date(2026, 11, 1), date(2026, 12, 31)),
            ("Модуль 3", date(2027, 1, 1), date(2027, 3, 15)),
            ("Модуль 4", date(2027, 3, 16), date(2027, 6, 30)),
        ]:
            Term.objects.create(year=year, name=name, starts_on=starts, ends_on=ends)
        for day, name in [
            (date(2026, 12, 8), "День Конституции"),
            (date(2027, 1, 1), "Новый год"),
            (date(2027, 1, 14), "День защитников Родины"),
            (date(2027, 3, 8), "Международный женский день"),
            (date(2027, 3, 21), "Навруз"),
        ]:
            Holiday.objects.create(date=day, name=name)

        subjects = {
            short: Subject.objects.create(name=n, short_name=short) for n, short in SUBJECTS
        }
        rooms = {name: Room.objects.create(name=name, capacity=cap) for name, cap in ROOMS}
        for teacher, shorts in zip(teachers, TEACHER_SUBJECTS, strict=True):
            teacher.teacher_profile.subjects.set([subjects[s] for s in shorts])

        lecture = LessonType.objects.get(short="Лк")
        practice = LessonType.objects.get(short="Пр")
        groups: dict[str, Group] = {}
        start = date(2026, 9, 1)
        for name, (level, courses) in GROUPS.items():
            group = Group.objects.create(name=name, academic_year=year, level=level)
            groups[name] = group
            for short, teacher_index, slots in courses:
                course = Course.objects.create(
                    group=group, subject=subjects[short], teacher=teachers[teacher_index]
                )
                for index, (weekday, begins, finishes, room) in enumerate(slots):
                    ScheduleSlot.objects.create(
                        course=course,
                        weekday=weekday,
                        start_time=begins,
                        end_time=finishes,
                        room=rooms[room],
                        valid_from=start,
                        lesson_type=lecture if index == 0 else practice,
                    )
        # An assistant: the physics teacher helps with weekend maths.
        weekend = groups["10-М выходного дня"]
        Course.objects.get(group=weekend, subject=subjects["Мат"]).assistants.add(teachers[1])

        # 15 students per group; three morning students also attend the weekend group.
        names = list(groups)
        for index, student in enumerate(students):
            group = groups[names[index // 15]]
            GroupMembership.objects.create(group=group, student=student, joined_on=start)
        for student in students[15:18]:
            GroupMembership.objects.create(group=weekend, student=student, joined_on=start)

        monday = today - timedelta(days=today.isoweekday() - 1)
        services.generate_lessons(
            first=monday - timedelta(weeks=4), last=today + timedelta(days=27)
        )
        self._exceptions(monday, groups, subjects, rooms, teachers)
        self._journal(today, groups, students)
        self._reviews(today)
        self._payments(today, groups, students)
        self._parents(students)
        self._exams(today, groups, subjects)
        self._announcements(groups)

    def _lesson(self, group: Group, subject: Subject, day: date) -> Lesson | None:
        return Lesson.objects.filter(course__group=group, course__subject=subject, date=day).first()

    def _exceptions(
        self,
        monday: date,
        groups: dict[str, Group],
        subjects: dict[str, Subject],
        rooms: dict[str, Room],
        teachers: list[User],
    ) -> None:
        """One of each: cancellation, move, substitution, extra lesson, pending request."""
        week = monday + timedelta(weeks=1)
        evening = groups["11-М вечерняя"]
        if lesson := self._lesson(evening, subjects["Физ"], week + timedelta(days=2)):
            lesson.status = LessonStatus.CANCELLED
            lesson.cancel_reason = "Преподаватель на олимпиаде"
            lesson.save()
        if lesson := self._lesson(evening, subjects["Мат"], week + timedelta(days=3)):
            lesson.date = week + timedelta(days=5)
            lesson.start_time, lesson.end_time = time(14), time(15, 30)
            lesson.save()
        if lesson := self._lesson(evening, subjects["Англ"], week + timedelta(days=1)):
            lesson.teacher = teachers[1]
            lesson.save()
        maths = Course.objects.get(group=groups["10-М выходного дня"], subject=subjects["Мат"])
        sunday = week + timedelta(days=6)
        hall = rooms["Актовый зал"]
        Lesson.objects.create(
            course=maths,
            date=sunday,
            start_time=time(14),
            end_time=time(15, 30),
            room=hall,
            teacher=maths.teacher,
            lesson_type=LessonType.objects.filter(short="Конс").first(),
            is_extra=True,
            planned_date=sunday,
            planned_start_time=time(14),
            planned_end_time=time(15, 30),
            planned_room=hall,
        )
        morning = groups["11-Б утренняя"]
        if lesson := self._lesson(morning, subjects["Био"], week + timedelta(days=3)):
            ScheduleRequest.objects.create(
                lesson=lesson,
                author=teachers[5],
                kind=ScheduleRequest.Kind.MOVE,
                proposed_date=week + timedelta(days=4),
                proposed_start_time=time(14, 15),
                proposed_end_time=time(15, 45),
                proposed_room=rooms["202"],
                reason="Лабораторная в университете",
            )

    # --- Journal (stage 3) -----------------------------------------------------------------

    TOPICS: ClassVar[dict[str, list[str]]] = {
        "Мат": ["Квадратные уравнения", "Теорема Виета", "Неравенства", "Модуль числа",
                "Прогрессии", "Логарифмы", "Тригонометрия", "Производная"],
        "Физ": ["Кинематика", "Законы Ньютона", "Импульс", "Работа и энергия",
                "Колебания", "Электростатика"],
        "Англ": ["Present Perfect", "Conditionals", "Reading: science", "Essay structure",
                 "Passive voice", "Vocabulary: education"],
        "Рус": ["Орфография: н и нн", "Пунктуация в сложном предложении", "Сочинение",
                "Причастный оборот", "Тест: орфоэпия"],
        "Хим": ["Строение атома", "Химическая связь", "Окислительно-восстановительные реакции",
                "Органика: алканы", "Растворы"],
        "Био": ["Клетка", "Генетика", "Эволюция", "Экосистемы", "Физиология человека"],
    }  # fmt: skip

    HOMEWORK: ClassVar[list[str]] = [
        "Повторить тему, задачи № {a}–{b}",
        "Конспект параграфа и упражнения № {a}–{b}",
        "Решить вариант пробного теста, задания {a}–{b}",
        "Выучить определения, письменно № {a} и {b}",
    ]

    def _journal(self, today: date, groups: dict[str, Group], students: list[User]) -> None:
        work = {w.name: w for w in WorkType.objects.all()}
        test_type = LessonType.objects.get(short="КР")
        weak_attendance = students[3]  # many absences → «Внимание»
        weak_grades = students[20]  # two low grades in a row → «Внимание»
        unfilled_group = groups["11-Г вечерняя"]
        lessons = (
            Lesson.objects.filter(date__lt=today)
            .exclude(status=LessonStatus.CANCELLED)
            .select_related("course__subject", "course__group", "lesson_type")
            .order_by("course_id", "date", "start_time")
        )
        members: dict[Any, list[tuple[Any, date, date | None]]] = {}
        for m in GroupMembership.objects.values_list(
            "group_id", "student_id", "joined_on", "left_on"
        ):
            members.setdefault(m[0], []).append((m[1], m[2], m[3]))
        attendance: list[Attendance] = []
        grades: list[Grade] = []
        seen: dict[Any, int] = {}
        for lesson in lessons:
            if lesson.course.group_id == unfilled_group.pk and lesson.date >= today - timedelta(
                days=3
            ):
                continue  # left for «Не заполнено»
            n = seen[lesson.course_id] = seen.get(lesson.course_id, 0) + 1
            topics = self.TOPICS[lesson.course.subject.short_name]
            lesson.topic = topics[(n - 1) % len(topics)]
            lesson.homework = self.HOMEWORK[n % len(self.HOMEWORK)].format(a=n * 3, b=n * 3 + 4)
            if n % 6 == 0:
                lesson.lesson_type = test_type
            lesson.status = LessonStatus.CONDUCTED
            lesson.save()
            is_test = lesson.lesson_type_id == test_type.pk
            for sid, joined, left in members.get(lesson.course.group_id, []):
                if not (joined <= lesson.date and (left is None or lesson.date <= left)):
                    continue
                roll = self.rng.random()
                if sid == weak_attendance.pk:
                    status = AttendanceStatus.ABSENT if roll < 0.45 else AttendanceStatus.PRESENT
                # Stage 19: only «был» and «н» for now (lateness and excused are switched off).
                elif roll < 0.9:
                    status = AttendanceStatus.PRESENT
                else:
                    status = AttendanceStatus.ABSENT
                attendance.append(
                    Attendance(
                        lesson=lesson,
                        student_id=sid,
                        status=status,
                        marked_by=lesson.teacher,
                        late_minutes=self.rng.randint(3, 20)
                        if status == AttendanceStatus.LATE
                        else None,
                    )
                )
                if status not in (AttendanceStatus.PRESENT, AttendanceStatus.LATE):
                    continue
                if not is_test and self.rng.random() > 0.6:  # a grade on most lessons
                    continue
                value = max(0, min(100, round(self.rng.gauss(74, 14))))
                if sid == weak_grades.pk and lesson.course.subject.short_name == "Хим":
                    value = self.rng.randint(25, 45)
                kind = work["Контрольная работа"] if is_test else work["Ответ на занятии"]
                grades.append(
                    Grade(
                        lesson=lesson,
                        student_id=sid,
                        value=value,
                        scale="100",
                        work_type=kind,
                        weight=kind.weight,
                        position=1,
                        created_by=lesson.teacher,
                    )
                )
        Attendance.objects.bulk_create(attendance)
        Grade.objects.bulk_create(grades)

    STRENGTHS: ClassVar[list[str]] = [
        "Внимательно решает задачи и доводит их до ответа.",
        "Хорошо работает на занятиях, задаёт точные вопросы.",
        "Уверенно знает теорию и объясняет её своими словами.",
        "Домашние задания выполняет полностью и в срок.",
    ]
    WEAKNESSES: ClassVar[list[str]] = [
        "Стоит больше практиковаться на задачах повышенной сложности.",
        "Теряет баллы на невнимательности — нужна проверка решений.",
        "Нужно подтянуть пропущенные темы и не опаздывать.",
        "Следующий шаг — решать задачи на время, как на экзамене.",
    ]

    def _reviews(self, today: date) -> None:
        """Stage 9: two sentences for a few students in the last finished term."""
        term = Term.objects.filter(ends_on__lt=today).order_by("-ends_on").first()
        if term is None:
            return
        reviews = []
        for course in Course.objects.select_related("teacher").order_by("group__name", "id"):
            members = (
                GroupMembership.objects.filter(group=course.group, joined_on__lte=term.ends_on)
                .exclude(left_on__lt=term.starts_on)
                .order_by("student__last_name", "student__first_name")
                .values_list("student_id", flat=True)[:4]
            )
            for sid in members:
                text = f"{self.rng.choice(self.STRENGTHS)} {self.rng.choice(self.WEAKNESSES)}"
                reviews.append(
                    TeacherReview(
                        course=course, student_id=sid, term=term, text=text, author=course.teacher
                    )
                )
        TeacherReview.objects.bulk_create(reviews)

    FEES: ClassVar[dict[str, int]] = {
        "11-М вечерняя": 600_000,
        "11-Б утренняя": 550_000,
        "11-Г вечерняя": 600_000,
        "10-М выходного дня": 450_000,
    }

    def _payments(self, today: date, groups: dict[str, Group], students: list[User]) -> None:
        """Stage 12: September to the current month billed; most of it paid."""
        admin = self.admin
        for name, amount in self.FEES.items():
            GroupFee.objects.create(group=groups[name], monthly_amount=amount)
        discounts = {students[5].pk: 10, students[30].pk: 20}
        for sid, percent in discounts.items():
            StudentDiscount.objects.create(student_id=sid, percent=percent)
        months = []
        first = date(2026, 9, 1)
        while first <= month_start(today):
            months.append(first)
            first = month_end(first) + timedelta(days=1)
        owes_two = students[3].pk
        charges, payments = [], []
        for name, amount in self.FEES.items():
            for m in GroupMembership.objects.filter(group=groups[name]):
                for first in months:
                    last = month_end(first)
                    if m.joined_on > last or (m.left_on and m.left_on < first):
                        continue
                    percent = discounts.get(m.student_id, 0)
                    due = discounted(amount, percent)
                    charges.append(
                        Charge(
                            student_id=m.student_id,
                            group=groups[name],
                            month=first,
                            full_amount=amount,
                            discount_percent=percent,
                            amount=due,
                            created_by=admin,
                        )
                    )
                    current = first == months[-1]
                    index = next(i for i, s in enumerate(students) if s.pk == m.student_id)
                    unpaid = (current and index % 4 == 0) or (
                        m.student_id == owes_two and first >= months[-2]
                    )
                    if unpaid:
                        continue
                    paid_on = min(first + timedelta(days=self.rng.randint(0, 9)), today)
                    payments.append(
                        Payment(
                            student_id=m.student_id,
                            amount=due,
                            paid_on=paid_on,
                            method=self.rng.choice(list(PaymentMethod)),
                            created_by=admin,
                        )
                    )
        Charge.objects.bulk_create(charges)
        Payment.objects.bulk_create(payments)

    @staticmethod
    def _surname(last: str, female: bool) -> str:
        """The family's surname in the right form: «Мирзаев» → «Мирзаева» for a woman."""
        for male_form, female_form in LAST_NAMES:
            if last in (male_form, female_form):
                return female_form if female else male_form
        return last

    def _parents(self, students: list[User]) -> None:
        """Stage 14: a mother of two (brother and sister of one family), two more parents."""
        families = [(students[0], students[1]), (students[3],), (students[20],)]
        for children in families:
            family = children[0].last_name
            for child in children[1:]:
                child.last_name = self._surname(family, child.first_name in FEMALE)
                child.save(update_fields=["last_name"])
            mother = self._make([Role.PARENT], self._surname(family, True), self.rng.choice(FEMALE))
            for child in children:
                ParentLink.objects.create(parent=mother, student=child)

    # --- Stage 5: mock exams and announcements ---------------------------------------------

    def _exams(self, today: date, groups: dict[str, Group], subjects: dict[str, Subject]) -> None:
        admin = self.admin
        evening = [groups["11-М вечерняя"], groups["11-Г вечерняя"]]
        maths = list(Course.objects.filter(group__in=evening, subject=subjects["Мат"]))
        english = list(
            Course.objects.filter(group=groups["11-М вечерняя"], subject=subjects["Англ"])
        )
        # (courses, title, days ago, max, sections); different maxima — the chart is in %.
        plan: list[tuple[list[Course], str, int, int, list[tuple[str, int]]]] = [
            (maths, "Пробный ДТМ № 1", 42, 30, []),
            (maths, "Пробный ДТМ № 2", 21, 30, []),
            (maths, "Пробный ДТМ № 3", 4, 100, [("Алгебра", 60), ("Геометрия", 40)]),
            (english, "Mock test 1", 30, 50, [("Reading", 25), ("Listening", 25)]),
            (english, "Mock test 2", 9, 50, [("Reading", 25), ("Listening", 25)]),
        ]
        ability: dict[Any, float] = {}
        for step, (courses, title, ago, maximum, sections) in enumerate(plan):
            exam = Exam.objects.create(
                title=title,
                subject=courses[0].subject,
                date=today - timedelta(days=ago),
                max_score=maximum,
                created_by=courses[0].teacher,
            )
            exam.courses.set(courses)
            parts = [
                ExamSection.objects.create(exam=exam, name=n, max_score=m, position=i)
                for i, (n, m) in enumerate(sections)
            ]
            members = GroupMembership.objects.filter(
                group__in=[c.group_id for c in courses], left_on__isnull=True
            ).values_list("student_id", flat=True)
            for sid in members:
                if self.rng.random() < 0.06:
                    ExamResult.objects.create(
                        exam=exam, student_id=sid, was_absent=True, entered_by=exam.created_by
                    )
                    continue
                base = ability.setdefault(sid, self.rng.uniform(0.45, 0.9))
                share = max(0.05, min(1.0, base + 0.03 * step + self.rng.gauss(0, 0.07)))
                scores = [
                    round(m * max(0.0, min(1.0, share + self.rng.gauss(0, 0.05))))
                    for _, m in sections
                ]
                total = sum(scores) if sections else round(maximum * share)
                result = ExamResult.objects.create(
                    exam=exam, student_id=sid, total=total, entered_by=exam.created_by
                )
                ExamSectionScore.objects.bulk_create(
                    ExamSectionScore(result=result, section=part, score=score)
                    for part, score in zip(parts, scores, strict=True)
                )
        upcoming = Exam.objects.create(
            title="Пробный ДТМ № 4",
            subject=subjects["Мат"],
            date=today + timedelta(days=12),
            max_score=100,
            created_by=admin,
        )
        upcoming.courses.set(maths)
        for sid in GroupMembership.objects.filter(group=evening[0]).values_list(
            "student_id", flat=True
        ):
            StudentTarget.objects.create(
                student_id=sid, subject=subjects["Мат"], percent=self.rng.choice([70, 75, 80, 85])
            )
            StudentTarget.objects.create(student_id=sid, subject=subjects["Англ"], percent=75)

    def _announcements(self, groups: dict[str, Group]) -> None:
        admin = self.admin
        now = timezone.now()
        Announcement.objects.create(
            author=admin,
            title="Зимние каникулы",
            body="С 30 декабря по 8 января занятий нет. Расписание на январь — в разделе "
            "«Расписание».",
            pinned=True,
        )
        Announcement.objects.create(
            author=admin,
            title="Пробный ДТМ № 4",
            body="Через две недели — пробный тест по математике. Начало в 10:00, кабинет 201.",
            audience=Audience.ROLE,
            role=Role.STUDENT,
        )
        Announcement.objects.create(
            author=admin,
            title="Журналы до пятницы",
            body="Пожалуйста, заполните все занятия прошлой недели до пятницы.",
            audience=Audience.ROLE,
            role=Role.TEACHER,
            pinned=True,
        )
        evening = Announcement.objects.create(
            author=admin,
            title="Родительское собрание",
            body="В субботу в 11:00 — собрание для родителей группы 11-М вечерняя.",
            audience=Audience.GROUPS,
        )
        evening.groups.set([groups["11-М вечерняя"]])
        Announcement.objects.create(
            author=admin,
            title="Старое объявление",
            body="Срок показа истёк — его видно только администратору в списке.",
            published_at=now - timedelta(days=20),
            expires_at=now - timedelta(days=10),
        )

    def _print(self) -> None:
        width = max(len(r[1]) for r in self.rows)
        self.stdout.write(f"{'роль':<8}  {'ФИО':<{width}}  {'логин':<14}  пароль")
        for roles, name, login, password in self.rows:
            self.stdout.write(f"{roles:<8}  {name:<{width}}  {login:<14}  {password}")
        self.stdout.write(
            self.style.SUCCESS(
                f"\nСоздано: суперадмин и завуч, 6 преподавателей, 60 учеников, 3 родителя, "
                f"{Group.objects.count()} группы, {Course.objects.count()} курсов, "
                f"{Lesson.objects.count()} занятий (4 недели назад и 4 вперёд), "
                f"{Attendance.objects.count()} отметок, {Grade.objects.count()} оценок, "
                f"{Exam.objects.count()} пробных тестов, "
                f"{Announcement.objects.count()} объявлений, "
                f"{TeacherReview.objects.count()} отзывов, "
                f"{Charge.objects.count()} начислений и {Payment.objects.count()} оплат, "
                f"{ParentLink.objects.count()} связей «родитель — ребёнок». "
                "2FA каждый включает сам в профиле."
            )
        )
