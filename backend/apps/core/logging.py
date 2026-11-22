"""Structured logs for production: one JSON object per line on stdout.

Only the message and safe context go out: no request bodies, headers or cookies are logged
anywhere in the app, so passwords, tokens and phones never reach the log.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

# Attributes every LogRecord has; anything else was passed via `extra=` and is kept.
_STANDARD = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}
# Django attaches the request to error records; its repr is long and may contain cookies.
_DROP = {"request", "args"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD and key not in _DROP:
                entry[key] = value if isinstance(value, (str, int, float, bool)) else str(value)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)
