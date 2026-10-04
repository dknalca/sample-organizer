from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from .models import SampleRecord

FIELDS = ["original_path", "destination_path", "filename", "extension", "library", "family",
          "category", "confidence", "manual_destination", "classification_reason", "action", "duplicate_hash",
          "duplicate_of", "renamed_due_to_collision", "error"]


def write_reports(records: list[SampleRecord], destination: Path) -> tuple[Path, Path]:
    csv_path = _available(destination / "organization_report.csv")
    json_path = _available(destination / "organization_report.json")
    rows = [_row(record) for record in records]
    with csv_path.open("x", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with json_path.open("x", encoding="utf-8") as stream:
        json.dump(rows, stream, ensure_ascii=False, indent=2)
    return csv_path, json_path


def _row(record: SampleRecord) -> dict:
    return {
        "original_path": str(record.original_path),
        "destination_path": record.destination_path,
        "filename": record.filename,
        "extension": record.extension,
        "library": record.library,
        "family": record.family,
        "category": record.category,
        "confidence": record.confidence,
        "manual_destination": str(record.manual_destination) if record.manual_destination is not None else "",
        "classification_reason": "; ".join(record.reasons),
        "action": record.action,
        "duplicate_hash": record.duplicate_hash,
        "duplicate_of": record.duplicate_of,
        "renamed_due_to_collision": record.renamed_due_to_collision,
        "error": record.error,
    }


def _available(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 100000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise OSError(f"No se pudo reservar un nombre de informe para {path.name}")
