from __future__ import annotations

import os
import shutil
from pathlib import Path
from collections.abc import Callable

from .models import OrganizationResult, SampleRecord, ScanResult
from .cancellation import CancellationToken, TaskCancelled
from .paths import is_within, validate_roots
from .reporting import write_reports


def destination_for(record: SampleRecord) -> Path | None:
    if record.kind not in {"audio", "midi"}:
        return None
    library = record.library or "Unknown Library"
    if record.family == "Unclassified":
        return Path("Unclassified") / library / record.filename
    category = record.category
    if record.family == "One Shots":
        if category.startswith("Drums/"):
            parts = ["One Shots", *category.split("/", 1)]
        elif category in {"Kick", "Snare", "Clap", "HiHat Closed", "HiHat Open", "HiHat", "Rim", "Tom", "Percussion", "Cymbal"}:
            parts = ["One Shots", "Drums", category]
        else:
            parts = ["One Shots", category]
    else:
        parts = [record.family, category]
    return Path(*parts, library, record.filename)


def organize(result: ScanResult, destination: Path, *, delete_pending: bool = False,
             progress: Callable[[int, str], None] | None = None,
             cancellation: CancellationToken | None = None) -> OrganizationResult:
    source, target = validate_roots(result.source, destination)
    target.mkdir(parents=True, exist_ok=True)
    outcome = OrganizationResult()
    for record in result.records:
        record.action = "skip"
    actionable = [r for r in result.records if r.kind in {"audio", "midi"} or r.is_pending_deletion]
    total = len(actionable)
    for index, record in enumerate(actionable, 1):
        if cancellation and cancellation.cancelled:
            outcome.cancelled = True
            break
        try:
            if cancellation:
                cancellation.check()
            if record.is_pending_deletion:
                if delete_pending:
                    if record.original_path.is_symlink():
                        raise ValueError("No se eliminan enlaces simbólicos")
                    original = record.original_path.resolve(strict=True)
                    if not is_within(original, source):
                        raise ValueError("Ruta pendiente de limpieza fuera del origen seguro")
                    original.unlink()
                    if record.pending_type == "part":
                        record.action = "delete_part"
                        outcome.deleted_parts += 1
                    elif record.pending_type == "lrc":
                        record.action = "delete_lrc"
                        outcome.deleted_lrc += 1
                    else:
                        record.action = "delete_macos_metadata"
                        outcome.deleted_macos_metadata += 1
                else:
                    record.action = "skip"
            else:
                relative = destination_for(record)
                if relative is None:
                    record.action = "skip"
                else:
                    wanted = target / relative
                    final = _copy_without_overwrite(record.original_path, wanted, target, cancellation)
                    record.destination_path = str(final)
                    record.renamed_due_to_collision = final.name != wanted.name
                    record.action = "copy"
                    outcome.copied += 1
        except TaskCancelled:
            outcome.cancelled = True
            record.action = "cancelled"
            break
        except Exception as exc:
            record.action = "error"
            record.error = str(exc)
            outcome.errors.append(f"{record.original_path}: {exc}")
        if progress:
            progress(index, f"{record.action}: {record.filename}")
    if outcome.cancelled:
        for record in actionable:
            if record.action == "skip":
                record.action = "cancelled"
    try:
        outcome.report_csv, outcome.report_json = write_reports(result.records, target)
    except OSError as exc:
        outcome.errors.append(f"No se pudieron generar los informes: {exc}")
    return outcome


def _copy_without_overwrite(source: Path, wanted: Path, destination_root: Path,
                            cancellation: CancellationToken | None = None) -> Path:
    if source.is_symlink():
        raise ValueError("No se copian enlaces simbólicos")
    _ensure_safe_parent(wanted.parent, destination_root)
    stem, suffix = wanted.stem, wanted.suffix
    for index in range(1, 100000):
        candidate = wanted if index == 1 else wanted.with_name(f"{stem}_{index}{suffix}")
        try:
            descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        except FileExistsError:
            continue
        try:
            with os.fdopen(descriptor, "wb") as target, source.open("rb") as original:
                while True:
                    if cancellation:
                        cancellation.check()
                    block = original.read(1024 * 1024)
                    if not block:
                        break
                    target.write(block)
            shutil.copystat(source, candidate, follow_symlinks=False)
            return candidate
        except Exception:
            try:
                candidate.unlink(missing_ok=True)
            finally:
                raise
    raise OSError(f"Demasiadas colisiones para {wanted.name}")


def _ensure_safe_parent(parent: Path, destination_root: Path) -> None:
    relative = parent.relative_to(destination_root)
    current = destination_root
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            raise ValueError(f"No se escribe a través de un enlace simbólico: {current}")
        current.mkdir(exist_ok=True)
        if not is_within(current, destination_root):
            raise ValueError(f"Ruta de destino fuera de la carpeta elegida: {current}")
