"""Administrator CRUD with the audit trail built in."""

from typing import Any, ClassVar

from django.db import IntegrityError, transaction
from django.db.models import Model, ProtectedError
from rest_framework import mixins, serializers, viewsets
from rest_framework.exceptions import APIException, ValidationError

from apps.accounts.permissions import IsAdmin
from apps.audit import services as audit


class InUse(APIException):
    status_code = 409
    default_detail = "in_use"
    default_code = "in_use"


class AuditedAdminViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,  # type: ignore[type-arg]
):
    """list / create / retrieve / PATCH / delete for administrators.

    Every write is audited in the same transaction. Deleting something still referenced
    answers 409 `in_use` (archive it instead). Database constraint violations become 400
    with `integrity_error` as the code.
    """

    permission_classes = (IsAdmin,)
    lookup_value_converter = "uuid"
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]  # noqa: RUF012
    audit_name: ClassVar[str] = ""
    integrity_error: ClassVar[str] = "integrity_error"
    # Database constraint name (substring) → API error code.
    constraint_codes: ClassVar[dict[str, str]] = {}

    def audit_fields(self) -> list[str]:
        meta = getattr(self.get_serializer_class(), "Meta")  # noqa: B009
        fields = getattr(meta, "fields", ())
        model = meta.model
        concrete = {f.name for f in model._meta.concrete_fields}
        return [f for f in fields if f in concrete and f != "id"]

    def snapshot(self, instance: Model) -> dict[str, Any]:
        data = audit.snapshot(instance, self.audit_fields())
        # Foreign keys as ids, not objects.
        for name, value in list(data.items()):
            if isinstance(value, Model):
                data[name] = str(value.pk)
        return data

    def _save(self, serializer: serializers.BaseSerializer[Any]) -> Model:
        try:
            with transaction.atomic():
                return serializer.save()  # type: ignore[no-any-return]
        except IntegrityError as exc:
            raise ValidationError({"non_field_errors": [self._code(exc)]}) from exc

    def _code(self, exc: IntegrityError) -> str:
        diag = getattr(exc.__cause__, "diag", None)
        name = getattr(diag, "constraint_name", None) or ""
        for fragment, code in self.constraint_codes.items():
            if fragment in name:
                return code
        return self.integrity_error

    def perform_create(self, serializer: serializers.BaseSerializer[Any]) -> None:
        with transaction.atomic():
            instance = self._save(serializer)
            self.after_create(instance)
            audit.record(
                request=self.request,
                action=f"{self.audit_name}.create",
                entity=instance,
                after=self.snapshot(instance),
            )

    def perform_update(self, serializer: serializers.BaseSerializer[Any]) -> None:
        if serializer.instance is None:
            raise RuntimeError("update without an instance")
        before = self.snapshot(serializer.instance)
        previous = type(serializer.instance).objects.get(pk=serializer.instance.pk)
        with transaction.atomic():
            instance = self._save(serializer)
            self.after_update(instance, previous)
            after = self.snapshot(instance)
            if after != before:
                audit.record(
                    request=self.request,
                    action=f"{self.audit_name}.update",
                    entity=instance,
                    before=before,
                    after=after,
                )

    def perform_destroy(self, instance: Model) -> None:
        before = self.snapshot(instance)
        try:
            with transaction.atomic():
                self.before_destroy(instance)
                pk = instance.pk
                instance.delete()
                audit.record(
                    request=self.request,
                    action=f"{self.audit_name}.delete",
                    entity_type=instance._meta.label_lower,
                    entity_id=str(pk),
                    before=before,
                )
                self.after_destroy(instance)
        except (ProtectedError, IntegrityError) as exc:
            raise InUse() from exc

    # Hooks for side effects that belong to the same transaction.
    def after_create(self, instance: Any) -> None: ...

    def after_update(self, instance: Any, previous: Any) -> None: ...

    def before_destroy(self, instance: Any) -> None: ...

    def after_destroy(self, instance: Any) -> None: ...
