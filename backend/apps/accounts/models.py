"""User model.

Stage 0 lays down only the skeleton: AUTH_USER_MODEL cannot be swapped after the first
migration. Roles, profiles, sessions and 2FA arrive in stage 1.
"""

import uuid
from typing import Any, ClassVar

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower


class UserManager(BaseUserManager["User"]):
    def get_by_natural_key(self, username: str | None) -> "User":
        return self.get(login__iexact=(username or "").strip())

    def create_user(self, login: str, password: str | None = None, **fields: Any) -> "User":
        user = self.model(login=login.strip().lower(), **fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    login = models.CharField(max_length=64, unique=True)
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "login"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["last_name", "first_name"]

    objects = UserManager()

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(Lower("login"), name="accounts_user_login_ci_unique"),
        ]

    def __str__(self) -> str:
        return self.login
