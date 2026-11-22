"""Generated logins and temporary passwords."""

import re
import secrets

from .models import User, normalize_login

# Russian and Uzbek Cyrillic → Latin, readable and keyboard-friendly.
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
}  # fmt: skip

# 12 characters without look-alikes: no 0/O/o, 1/l/I.
TEMP_PASSWORD_ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TEMP_PASSWORD_LENGTH = 12

LOGIN_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,62}[a-z0-9]$")


def transliterate(text: str) -> str:
    result = "".join(_TRANSLIT.get(ch, ch) for ch in text.strip().lower())
    return re.sub(r"[^a-z0-9]", "", result)


def login_base(last_name: str, first_name: str) -> str:
    """«Алиев Фарход» → «aliev.f»."""
    last = transliterate(last_name) or "user"
    first = transliterate(first_name)[:1]
    return f"{last}.{first}" if first else last


def generate_login(last_name: str, first_name: str) -> str:
    """aliev.f, then aliev.f2, aliev.f3… Archived users keep their logins forever."""
    base = login_base(last_name, first_name)
    taken = set(
        User.objects.filter(login__regex=rf"^{re.escape(base)}[0-9]*$").values_list(
            "login", flat=True
        )
    )
    if base not in taken:
        return base
    n = 2
    while f"{base}{n}" in taken:
        n += 1
    return f"{base}{n}"


def is_valid_login(value: str) -> bool:
    return bool(LOGIN_RE.match(normalize_login(value)))


def generate_temporary_password() -> str:
    return "".join(secrets.choice(TEMP_PASSWORD_ALPHABET) for _ in range(TEMP_PASSWORD_LENGTH))
