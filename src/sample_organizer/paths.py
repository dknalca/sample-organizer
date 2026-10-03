from __future__ import annotations

import os
from pathlib import Path


def resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def is_within(path: Path, parent: Path) -> bool:
    try:
        resolved(path).relative_to(resolved(parent))
        return True
    except ValueError:
        return False


def validate_roots(source: Path, destination: Path) -> tuple[Path, Path]:
    src, dst = resolved(source), resolved(destination)
    if not src.is_dir():
        raise ValueError("La carpeta de origen no existe o no es una carpeta.")
    if src == dst:
        raise ValueError("El origen y el destino no pueden ser la misma carpeta.")
    if is_within(dst, src):
        raise ValueError("El destino está dentro del origen y produciría una recursión.")
    return src, dst


def safe_relative(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return Path(os.path.basename(path))
