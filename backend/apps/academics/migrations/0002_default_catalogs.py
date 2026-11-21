"""Default catalogs from SPEC §5: work types with weights and lesson types."""

from decimal import Decimal
from typing import Any

from django.db import migrations

WORK_TYPES = [
    ("Ответ на занятии", Decimal("1")),
    ("Домашнее задание", Decimal("1")),
    ("Самостоятельная работа", Decimal("1.5")),
    ("Контрольная работа", Decimal("2")),
]

# name, short, default work type, counts attendance
LESSON_TYPES = [
    ("Лекция", "Лк", "Ответ на занятии", True),
    ("Практика", "Пр", "Ответ на занятии", True),
    ("Семинар", "Сем", "Ответ на занятии", True),
    ("Контрольная", "КР", "Контрольная работа", True),
    ("Пробный тест", "ПТ", "Контрольная работа", True),
    ("Консультация", "Конс", "Ответ на занятии", False),
    ("Повторение", "Повт", "Ответ на занятии", True),
]


def forward(apps: Any, schema_editor: Any) -> None:
    WorkType = apps.get_model("academics", "WorkType")
    LessonType = apps.get_model("academics", "LessonType")
    work = {name: WorkType.objects.create(name=name, weight=weight) for name, weight in WORK_TYPES}
    for order, (name, short, work_name, counts) in enumerate(LESSON_TYPES):
        LessonType.objects.create(
            name=name,
            short=short,
            default_work_type=work[work_name],
            counts_attendance=counts,
            sort_order=order,
        )


def backward(apps: Any, schema_editor: Any) -> None:
    apps.get_model("academics", "LessonType").objects.all().delete()
    apps.get_model("academics", "WorkType").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("academics", "0001_initial")]

    operations = [migrations.RunPython(forward, backward)]
