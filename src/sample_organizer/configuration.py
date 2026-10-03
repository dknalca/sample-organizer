from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "categories.json"


def load_config(path: Path | None = None) -> dict:
    candidates = [path] if path else [DEFAULT_CONFIG]
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root) / "config" / "categories.json")
    for config_path in candidates:
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
    raise FileNotFoundError("No se encontró config/categories.json")
