from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SampleRecord:
    original_path: Path
    filename: str
    extension: str
    family: str = "Other files"
    category: str = ""
    library: str = "Unknown Library"
    confidence: str = "low"
    reasons: list[str] = field(default_factory=list)
    kind: str = "other"
    duplicate_hash: str = ""
    duplicate_of: str = ""
    error: str = ""
    destination_path: str = ""
    manual_destination: Path | None = None
    action: str = ""
    renamed_due_to_collision: bool = False

    @property
    def is_part(self) -> bool:
        return self.filename.casefold().endswith(".part")

    @property
    def is_lrc(self) -> bool:
        return self.filename.casefold().endswith(".lrc")

    @property
    def is_macos_metadata(self) -> bool:
        name = self.filename.casefold()
        return name == ".ds_store" or name.startswith("._") or name in {
            ".apdisk", ".lsoverride", ".localized",
        }

    @property
    def pending_type(self) -> str:
        if self.is_part:
            return "part"
        if self.is_lrc:
            return "lrc"
        if self.is_macos_metadata:
            return "macos_metadata"
        return ""

    @property
    def is_pending_deletion(self) -> bool:
        return bool(self.pending_type)


@dataclass
class ScanResult:
    source: Path
    records: list[SampleRecord]
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, int]:
        return {
            "files_found": len(self.records),
            "one_shots": sum(r.family == "One Shots" for r in self.records),
            "loops": sum(r.family == "Loops" for r in self.records),
            "midi": sum(r.family == "MIDI" for r in self.records),
            "unclassified": sum(r.family == "Unclassified" for r in self.records),
            "part": sum(r.is_part for r in self.records),
            "lrc": sum(r.is_lrc for r in self.records),
            "macos_metadata": sum(r.is_macos_metadata for r in self.records),
            "pending_deletion": sum(r.is_pending_deletion for r in self.records),
            "duplicates": sum(bool(r.duplicate_of) for r in self.records),
            "other": sum(r.kind not in {"audio", "midi", "part", "lrc", "macos_metadata"}
                          for r in self.records),
            "archives": sum(r.kind == "archive" for r in self.records),
        }


@dataclass
class OrganizationResult:
    copied: int = 0
    deleted_parts: int = 0
    deleted_lrc: int = 0
    deleted_macos_metadata: int = 0
    cancelled: bool = False
    errors: list[str] = field(default_factory=list)
    report_csv: Path | None = None
    report_json: Path | None = None
