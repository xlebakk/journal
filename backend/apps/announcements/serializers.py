from typing import Any

from rest_framework import serializers

from apps.academics.models import Group
from apps.accounts.permissions import current_user

from .models import Announcement, Audience


class AnnouncementSerializer(serializers.ModelSerializer[Announcement]):
    """The administrator's form. The author is the current user; the body is plain text."""

    author_name = serializers.CharField(source="author.short_name", read_only=True)
    groups = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(), many=True, required=False
    )
    group_names = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = (
            "id",
            "title",
            "body",
            "audience",
            "role",
            "groups",
            "group_names",
            "pinned",
            "published_at",
            "expires_at",
            "author_name",
            "created_at",
        )
        read_only_fields = ("id", "author_name", "created_at", "group_names")

    def get_group_names(self, obj: Announcement) -> list[str]:
        return [g.name for g in obj.groups.all()]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        merged = {
            name: attrs.get(name, getattr(self.instance, name, None))
            for name in ("audience", "role", "published_at", "expires_at")
        }
        groups = attrs.get("groups")
        if groups is None and self.instance is not None:
            groups = list(self.instance.groups.all())
        audience = merged["audience"] or Audience.ALL
        if audience == Audience.ROLE and merged["role"] not in ("teacher", "student"):
            raise serializers.ValidationError({"role": ["role_required"]})
        if audience == Audience.GROUPS and not groups:
            raise serializers.ValidationError({"groups": ["groups_required"]})
        if audience != Audience.ROLE:
            attrs["role"] = ""
        if audience != Audience.GROUPS and "groups" in attrs:
            attrs["groups"] = []
        expires, published = merged["expires_at"], merged["published_at"]
        if expires is not None and published is not None and expires <= published:
            raise serializers.ValidationError({"expires_at": ["expires_before_published"]})
        return attrs

    def create(self, validated_data: dict[str, Any]) -> Announcement:
        validated_data["author"] = current_user(self.context["request"])
        return super().create(validated_data)


class FeedItemSerializer(serializers.ModelSerializer[Announcement]):
    """What a reader sees: no audience details."""

    author_name = serializers.CharField(source="author.short_name", read_only=True)

    class Meta:
        model = Announcement
        fields = ("id", "title", "body", "pinned", "published_at", "author_name")
        read_only_fields = fields
