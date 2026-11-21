"""TOTP 2FA: encrypted secrets, replay-safe verification, one-time backup codes."""

import base64
import io
import secrets

import pyotp
import segno
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import BackupCode, User

BACKUP_CODE_COUNT = 10
# No look-alike characters (0/O, 1/l/I).
BACKUP_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
_HMAC_SALT = "apps.accounts.totp.backup-code"


def _fernet() -> MultiFernet:
    keys = settings.TOTP_ENCRYPTION_KEYS
    if not keys:
        raise ImproperlyConfigured("TOTP_ENCRYPTION_KEYS is not set")
    return MultiFernet([Fernet(key.encode()) for key in keys])


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ImproperlyConfigured("Cannot decrypt TOTP secret: wrong key") from exc


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(user: User, secret: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=user.login, issuer_name=settings.TOTP_ISSUER)


def qr_svg_data_uri(uri: str) -> str:
    """QR as a data: URI — allowed by CSP img-src, no inline markup needed."""
    buffer = io.BytesIO()
    segno.make(uri, error="m").save(buffer, kind="svg", scale=5, border=2, xmldecl=False)
    return "data:image/svg+xml;base64," + base64.b64encode(buffer.getvalue()).decode()


def matching_counter(secret: str, code: str) -> int | None:
    """Time step of a valid code (±1 step for clock drift), or None."""
    code = code.strip().replace(" ", "")
    if len(code) != 6 or not code.isdigit():
        return None
    totp = pyotp.TOTP(secret)
    now = timezone.now()
    for drift in (0, -1, 1):
        at = now.timestamp() + drift * totp.interval
        if constant_time_compare(totp.at(at), code):
            return int(at // totp.interval)
    return None


def verify_totp(user: User, code: str) -> bool:
    """Checks the code and remembers its time step so it cannot be replayed."""
    if not user.totp_enabled or not user.totp_secret:
        return False
    counter = matching_counter(decrypt_secret(user.totp_secret), code)
    if counter is None:
        return False
    if user.totp_last_counter is not None and counter <= user.totp_last_counter:
        return False
    updated = (
        User.objects.filter(pk=user.pk)
        .exclude(totp_last_counter__gte=counter)
        .update(totp_last_counter=counter)
    )
    user.totp_last_counter = counter
    return updated == 1


def _hash_code(code: str) -> str:
    normalized = code.strip().lower().replace("-", "").replace(" ", "")
    return salted_hmac(_HMAC_SALT, normalized, algorithm="sha256").hexdigest()


def generate_backup_codes(user: User) -> list[str]:
    """Replaces all backup codes; the plain codes are shown to the user once."""
    codes = [
        "".join(secrets.choice(BACKUP_ALPHABET) for _ in range(4))
        + "-"
        + "".join(secrets.choice(BACKUP_ALPHABET) for _ in range(4))
        for _ in range(BACKUP_CODE_COUNT)
    ]
    BackupCode.objects.filter(user=user).delete()
    BackupCode.objects.bulk_create(BackupCode(user=user, code_hash=_hash_code(c)) for c in codes)
    return codes


def use_backup_code(user: User, code: str) -> bool:
    updated = BackupCode.objects.filter(
        user=user, code_hash=_hash_code(code), used_at__isnull=True
    ).update(used_at=timezone.now())
    return updated == 1


def looks_like_backup_code(code: str) -> bool:
    return len(code.strip().replace("-", "")) == 8
