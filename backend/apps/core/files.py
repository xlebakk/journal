"""Reading uploaded tables and writing exports safely.

* Uploads: size limit, the real type is checked by content (XLSX is a ZIP), XLSX is read
  in read-only mode with cached values only (no formulas are evaluated) — openpyxl uses
  defusedxml when it is installed.
* Exports: cells that start with = + - @ (or a tab / CR) are prefixed with an apostrophe so
  a spreadsheet never runs them as formulas.
"""

import csv
import io
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import defusedxml  # noqa: F401 — must be importable: openpyxl switches to it automatically
from django.conf import settings
from django.http import HttpResponse
from openpyxl import Workbook, load_workbook
from rest_framework.exceptions import ValidationError

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _normalise(header: Any) -> str:
    return " ".join(str(header or "").replace("*", "").split()).lower()


def read_table(upload: Any) -> list[dict[str, str]]:
    """Rows of an uploaded CSV or XLSX as dicts keyed by the lower-cased header."""
    if upload is None:
        raise ValidationError({"file": ["required"]})
    if upload.size > settings.IMPORT_MAX_BYTES:
        raise ValidationError({"file": ["file_too_large"]})
    data = upload.read()
    if data[:4] == b"PK\x03\x04":
        rows = _read_xlsx(data)
    elif b"\x00" in data[:4096]:
        raise ValidationError({"file": ["unsupported_file"]})
    else:
        rows = _read_csv(data)
    if not rows:
        raise ValidationError({"file": ["empty_file"]})
    header = [_normalise(h) for h in rows[0]]
    result = []
    for raw in rows[1:]:
        cells = ["" if v is None else str(v).strip() for v in raw]
        if not any(cells):
            continue
        result.append({header[i]: cells[i] if i < len(cells) else "" for i in range(len(header))})
    return result


def _read_xlsx(data: bytes) -> list[Sequence[Any]]:
    try:
        book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # zip, XML or format errors: never trust the file
        raise ValidationError({"file": ["unsupported_file"]}) from exc
    sheet = book.worksheets[0]
    rows: list[Sequence[Any]] = []
    for row in sheet.iter_rows(values_only=True):
        rows.append([_cell_text(v) for v in row])
        if len(rows) > 5000:
            raise ValidationError({"file": ["too_many_rows"]})
    book.close()
    return rows


def _cell_text(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return None if value is None else str(value)


def _read_csv(data: bytes) -> list[Sequence[Any]]:
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValidationError({"file": ["unsupported_file"]})
    sample = text[:2048]
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    rows: list[Sequence[Any]] = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    if len(rows) > 5001:
        raise ValidationError({"file": ["too_many_rows"]})
    return rows


def safe_cell(value: Any) -> Any:
    """Formula-injection guard for exported cells."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str) and value.startswith(FORMULA_START):
        return "'" + value
    return value


def xlsx_response(
    filename: str, sheets: Iterable[tuple[str, Sequence[Sequence[Any]]]]
) -> HttpResponse:
    book = Workbook()
    book.remove(book.worksheets[0])
    for title, rows in sheets:
        sheet = book.create_sheet(title=title[:31])
        for row in rows:
            sheet.append([safe_cell(v) for v in row])
    buffer = io.BytesIO()
    book.save(buffer)
    response = HttpResponse(buffer.getvalue(), content_type=XLSX_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
    return response


def csv_response(filename: str, rows: Sequence[Sequence[Any]]) -> HttpResponse:
    """Semicolon-separated UTF-8 with BOM: opens correctly in Excel with a Russian locale."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    for row in rows:
        writer.writerow(["" if v is None else safe_cell(v) for v in row])
    response = HttpResponse(
        ("﻿" + buffer.getvalue()).encode("utf-8"), content_type="text/csv; charset=utf-8"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    return response


def export_kind(request: Any) -> str | None:
    """?export=xlsx|csv → a file; no parameter → JSON for the screen and print."""
    kind = request.query_params.get("export") or None
    if kind not in (None, "xlsx", "csv"):
        raise ValidationError({"export": ["invalid_choice"]})
    return kind


def export(
    kind: str, filename: str, sheets: Sequence[tuple[str, Sequence[Sequence[Any]]]]
) -> HttpResponse:
    """CSV carries the first sheet only."""
    if kind == "csv":
        return csv_response(filename, sheets[0][1])
    return xlsx_response(filename, sheets)
