"""Parents (SPEC §16.1, stage 14). The administrator adds a parent from the student's card:
a new account with a temporary password, or an existing parent (brothers and sisters).
A parent sees their children's student pages, read-only (`permissions.subject_student`)."""

from typing import Any

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.serializers import current_groups_of
from apps.audit import services as audit

from . import credentials
from .models import ParentLink, Role, User
from .permissions import IsAdmin, IsParent, children_of, current_user


class FamilyMemberSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    full_name = serializers.CharField()
    login = serializers.CharField()
    is_active = serializers.BooleanField()


class ParentAddSerializer(serializers.Serializer[Any]):
    """Either `existing` (a parent account already in the system) or the name of a new one."""

    existing = serializers.UUIDField(required=False)
    last_name = serializers.CharField(max_length=100, required=False)
    first_name = serializers.CharField(max_length=100, required=False)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    login = serializers.CharField(max_length=64, required=False, allow_blank=True)

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        if data.get("existing"):
            return data
        if not (data.get("last_name", "").strip() and data.get("first_name", "").strip()):
            raise serializers.ValidationError({"last_name": ["required"]})
        login = data.get("login", "").strip()
        if login and not credentials.is_valid_login(login):
            raise serializers.ValidationError({"login": ["invalid_login"]})
        return data


class ParentAddedSerializer(serializers.Serializer[Any]):
    parent = FamilyMemberSerializer()
    temporary_password = serializers.CharField(allow_null=True)


class ChildSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    full_name = serializers.CharField()
    short_name = serializers.CharField()
    groups = serializers.ListField(child=serializers.CharField())


def family_row(user: User) -> dict[str, Any]:
    return {
        "id": user.pk,
        "full_name": user.full_name,
        "login": user.login,
        "is_active": user.can_log_in,
    }


def _student(pk: str) -> User:
    return get_object_or_404(User.objects.with_role(Role.STUDENT), pk=pk)


def _link(request: Request, parent: User, student: User) -> None:
    try:
        with transaction.atomic():
            ParentLink.objects.create(parent=parent, student=student)
    except IntegrityError as exc:
        raise serializers.ValidationError({"existing": ["already_linked"]}) from exc
    audit.record(
        request=request,
        action="parent.link",
        entity=student,
        after={"parent": str(parent.pk), "parent_name": parent.full_name},
    )


def _new_parent(request: Request, data: dict[str, Any]) -> tuple[User, str]:
    password = credentials.generate_temporary_password()
    for _attempt in range(3):
        login = data.get("login") or credentials.generate_login(
            data["last_name"], data["first_name"]
        )
        try:
            with transaction.atomic():
                parent = User.objects.create_user(
                    login=login,
                    password=password,
                    last_name=data["last_name"].strip(),
                    first_name=data["first_name"].strip(),
                    middle_name=data.get("middle_name", "").strip(),
                    roles=[Role.PARENT],
                    must_change_password=True,
                )
            break
        except IntegrityError as exc:
            if data.get("login"):
                raise serializers.ValidationError({"login": ["login_taken"]}) from exc
    else:
        raise serializers.ValidationError({"login": ["login_taken"]})
    audit.record(
        request=request,
        action="user.create",
        entity=parent,
        after={"login": parent.login, "roles": parent.roles, "full_name": parent.full_name},
    )
    return parent, password


class StudentParentsView(APIView):
    """`/admin/users/<student>/parents`: who can see this student's pages."""

    permission_classes = (IsAdmin,)

    @extend_schema(responses=FamilyMemberSerializer(many=True))
    def get(self, request: Request, pk: str) -> Response:
        student = _student(pk)
        parents = User.objects.filter(children_links__student=student).order_by(
            "last_name", "first_name"
        )
        return Response(FamilyMemberSerializer([family_row(p) for p in parents], many=True).data)

    @extend_schema(request=ParentAddSerializer, responses={201: ParentAddedSerializer})
    def post(self, request: Request, pk: str) -> Response:
        student = _student(pk)
        form = ParentAddSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        password: str | None = None
        with transaction.atomic():
            if data.get("existing"):
                parent = get_object_or_404(User.objects.with_role(Role.PARENT), pk=data["existing"])
            else:
                parent, password = _new_parent(request, data)
            _link(request, parent, student)
        body = {"parent": family_row(parent), "temporary_password": password}
        return Response(ParentAddedSerializer(body).data, status=status.HTTP_201_CREATED)


class StudentParentView(APIView):
    permission_classes = (IsAdmin,)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, pk: str, parent_id: str) -> Response:
        student = _student(pk)
        with transaction.atomic():
            link = get_object_or_404(ParentLink, student=student, parent_id=parent_id)
            link.delete()
            audit.record(
                request=request,
                action="parent.unlink",
                entity=student,
                before={"parent": str(parent_id)},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ParentChildrenAdminView(APIView):
    """`/admin/users/<parent>/children`: the parent's card lists the children."""

    permission_classes = (IsAdmin,)

    @extend_schema(responses=FamilyMemberSerializer(many=True))
    def get(self, request: Request, pk: str) -> Response:
        parent = get_object_or_404(User.objects.with_role(Role.PARENT), pk=pk)
        children = children_of(parent).order_by("last_name", "first_name")
        return Response(FamilyMemberSerializer([family_row(c) for c in children], many=True).data)


class MyChildrenView(APIView):
    """`/parent/children`: whom the parent can look at; the switch in the header."""

    permission_classes = (IsParent,)

    @extend_schema(responses=ChildSerializer(many=True))
    def get(self, request: Request) -> Response:
        children = children_of(current_user(request)).order_by("last_name", "first_name")
        rows = [
            {
                "id": c.pk,
                "full_name": c.full_name,
                "short_name": c.short_name,
                "groups": [g["name"] for g in current_groups_of(c)],
            }
            for c in children
        ]
        return Response(ChildSerializer(rows, many=True).data)
