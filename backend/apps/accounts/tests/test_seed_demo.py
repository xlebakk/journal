from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.test import override_settings

from apps.accounts.models import Role, User


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_seed_demo_creates_people_and_prints_passwords() -> None:
    out = StringIO()
    call_command("seed_demo", stdout=out)
    assert User.objects.with_role(Role.ADMIN).count() == 1
    assert User.objects.with_role(Role.TEACHER).count() == 6
    assert User.objects.with_role(Role.STUDENT).count() == 60
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
