from __future__ import annotations

import os
import hashlib
import time
from pathlib import Path
from collections.abc import Callable

from .classifier import classify
from .cancellation import CancellationToken
from .configuration import load_config
from .models import SampleRecord, ScanResult
from .paths import resolved, validate_roots


def scan(source: Path, destination: Path | None = None,
         progress: Callable[[int, str], None] | None = None,
         config: dict | None = None,
         cancellation: CancellationToken | None = None) -> ScanResult:
    src = resolved(source)
    dst = resolved(destination) if destination else None
    if not src.is_dir():
        raise ValueError("La carpeta de origen no existe o no es una carpeta.")
    if dst is not None and (src == dst or _within(dst, src)):
        raise ValueError("El destino no puede ser el origen ni estar dentro del origen.")

    settings = config or load_config()
    records: list[SampleRecord] = []
    errors: list[str] = []
    last_directory_update = 0.0
    if progress:
        progress(0, "Escaneando archivos…")
    for current, dirs, files in os.walk(src, followlinks=False, onerror=lambda e: errors.append(str(e))):
        if cancellation:
            cancellation.check()
        current_path = Path(current)
        now = time.monotonic()
        if progress and (last_directory_update == 0.0 or now - last_directory_update >= 0.15):
            progress(len(records), f"Analizando directorio: {current_path}")
            last_directory_update = now
        dirs[:] = sorted(d for d in dirs if not (current_path / d).is_symlink()
                         and not (dst and _within(current_path / d, dst)))
        for name in files:
            if cancellation:
                cancellation.check()
            path = current_path / name
            if path.is_symlink():
                continue
            record = classify(path, src, settings)
            records.append(record)
            if progress and len(records) % 100 == 0:
                progress(len(records), f"Escaneando: {path.name} ({len(records)} archivos)")
    if progress:
        progress(len(records), f"Escaneo completo: {len(records)} archivos; comprobando duplicados…")
    detect_duplicates(records, progress, cancellation=cancellation)
    if progress:
        progress(len(records), f"Análisis finalizado: {len(records)} archivos")
    return ScanResult(src, records, errors)


def _within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def detect_duplicates(records: list[SampleRecord],
                      progress: Callable[[int, str], None] | None = None,
                      chunk_size: int = 1024 * 1024,
                      cancellation: CancellationToken | None = None) -> None:
    """Hash same-sized files by streaming; only candidates share the same size."""
    groups: dict[int, list[SampleRecord]] = {}
    for record in records:
        if not record.is_pending_deletion:
            try:
                groups.setdefault(record.original_path.stat().st_size, []).append(record)
            except OSError as exc:
                record.error = str(exc)
    candidates_to_hash = [(size, record) for size, candidates in groups.items() if len(candidates) > 1
                          for record in candidates]
    total = len(candidates_to_hash)
    if progress:
        progress(0, f"Comparando duplicados: {total} archivos con tamaños coincidentes…")
    processed = 0
    seen: dict[tuple[int, str], SampleRecord] = {}
    for size, record in candidates_to_hash:
        if cancellation:
            cancellation.check()
        digest = hashlib.sha256()
        started = time.monotonic()
        last_notice = started
        if progress and (processed == 0 or processed % 20 == 0):
            progress(processed, f"Calculando hash: {record.filename} ({processed + 1}/{total})")
        try:
            bytes_read = 0
            with record.original_path.open("rb") as stream:
                while block := stream.read(chunk_size):
                    if cancellation:
                        cancellation.check()
                    digest.update(block)
                    bytes_read += len(block)
                    now = time.monotonic()
                    if progress and now - last_notice >= 0.5:
                        progress(processed, f"Calculando hash: {record.filename} ({bytes_read // (1024 * 1024)} MB)")
                        last_notice = now
            record.duplicate_hash = digest.hexdigest()
            key = (size, record.duplicate_hash)
            previous = seen.get(key)
            if previous:
                record.duplicate_of = str(previous.original_path)
            else:
                seen[key] = record
        except OSError as exc:
            record.error = str(exc)
        processed += 1
        if progress and (processed % 20 == 0 or processed == total):
            progress(processed, f"Comprobados hashes: {processed}/{total}")
