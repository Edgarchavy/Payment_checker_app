from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import csv
import json

from .xlsx_writer import write_xlsx


def ensure_dir(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def rows_to_dicts(rows: list[object]) -> list[dict]:
    return [asdict(item) for item in rows]


def write_csv(path: str | Path, rows: list[object]) -> None:
    dict_rows = rows_to_dicts(rows)
    path = Path(path)
    if not dict_rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(dict_rows[0].keys()))
        writer.writeheader()
        writer.writerows(dict_rows)


def write_json(path: str | Path, rows: list[object]) -> None:
    path = Path(path)
    path.write_text(json.dumps(rows_to_dicts(rows), ensure_ascii=False, indent=2), encoding="utf-8")


def write_xlsx_from_rows(path: str | Path, rows: list[object], widths: dict[int, int] | None = None, title: str = "Coursework output") -> None:
    dict_rows = rows_to_dicts(rows)
    if not dict_rows:
        return
    headers = list(dict_rows[0].keys())
    table_rows = [headers]
    for row in dict_rows:
        table_rows.append([str(row[key]) for key in headers])
    write_xlsx(path=path, rows=table_rows, widths=widths, title=title)
