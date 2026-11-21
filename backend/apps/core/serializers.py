"""Model serializers that leave uniqueness to the database.

DRF builds its own unique validators from model constraints and answers with translated
sentences; this API answers with codes instead (see core.viewsets: constraint → code).
"""

from typing import Any, TypeVar

from django.db.models import Model
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator, UniqueValidator

M = TypeVar("M", bound=Model)


class DatabaseUniqueModelSerializer(serializers.ModelSerializer[M]):
    def get_fields(self) -> dict[str, serializers.Field[Any, Any, Any, Any]]:
        fields = super().get_fields()
        for field in fields.values():
            field.validators = [v for v in field.validators if not isinstance(v, UniqueValidator)]
        return fields

    def get_validators(self) -> list[Any]:
        return [v for v in super().get_validators() if not isinstance(v, UniqueTogetherValidator)]
