from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from .configuration import load_config
from .models import SampleRecord

GENERIC = {
    "loop", "loops", "one shot", "one shots", "oneshot", "oneshots", "drum", "drums",
    "bass", "kick", "kicks", "snare", "snares", "midi", "audio", "sample", "samples",
    "wav", "wavs", "flac", "aiff", "aif", "mp3", "percussion", "synth", "keys",
    "guitar", "vocal", "vocals", "fx", "other", "chords", "melody", "arpeggio", "lyric", "lyrics",
}
FAMILY_MARKERS = {
    "Loops": {"loop", "loops"},
    "One Shots": {"one shot", "one shots", "oneshot", "oneshots"},
    "MIDI": {"midi"},
}


@lru_cache(maxsize=8192)
def normalize(value: str) -> str:
    value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"[_-]+", " ", value.casefold())
    return re.sub(r"[^\w\s]+", " ", value, flags=re.UNICODE).strip()


def _matches(text: str, alias: str) -> bool:
    t, a = f" {normalize(text)} ", f" {normalize(alias)} "
    return a in t


def _family_marker(directory: str) -> str:
    words = normalize(directory)
    if re.search(r"\b(?:one shots?|oneshots?)\b", words):
        return "One Shots"
    if re.search(r"\bloops?\b", words):
        return "Loops"
    return ""


def _filename_family(filename: str) -> str:
    words = normalize(Path(filename).stem)
    if re.search(r"\b(?:one shots?|oneshots?)\b", words):
        return "One Shots"
    if re.search(r"\bloops?\b", words) or re.search(r"\w+loops?\b", words):
        return "Loops"
    return ""


def detect_library(path: Path, root: Path) -> tuple[str, str, str]:
    relative_dirs = list(path.relative_to(root).parts[:-1])
    family_index = next((index for index, directory in enumerate(relative_dirs)
                         if _family_marker(directory) or normalize(directory) == "midi"), len(relative_dirs))
    candidates = [d for d in relative_dirs[:family_index] if normalize(d) not in GENERIC]
    if candidates:
        return candidates[-1], "high" if len(candidates) > 0 else "medium", "Carpeta de librería: " + candidates[-1]
    if relative_dirs:
        return relative_dirs[0], "low", "Nombre derivado de una carpeta estructural; revisar librería"
    return "Unknown Library", "low", "No se encontró una carpeta de librería identificable"


def classify(path: Path, root: Path, config: dict | None = None) -> SampleRecord:
    settings = config or load_config()
    name = path.name
    ext = path.suffix.casefold()
    record = SampleRecord(original_path=path, filename=name, extension=ext)
    library, library_confidence, library_reason = detect_library(path, root)
    record.library = library
    record.reasons.append(library_reason)
    if name.casefold().endswith(".part"):
        record.family, record.kind, record.confidence = "Pending deletion", "part", "low"
        record.reasons.append("Archivo .part posiblemente incompleto; pendiente de decisión")
        return record
    if ext == ".lrc":
        record.family, record.kind, record.confidence = "Pending deletion", "lrc", "low"
        record.reasons.append("Archivo de letras .lrc; pendiente de decisión para eliminar")
        return record
    if record.is_macos_metadata:
        record.family, record.kind, record.confidence = "Pending deletion", "macos_metadata", "low"
        record.reasons.append("Archivo auxiliar de metadatos macOS; pendiente de decisión para eliminar")
        return record

    extensions = settings.get("extensions", {})
    if ext in extensions.get("archives", []):
        record.kind, record.family = "archive", "Archives"
        record.reasons.append("Extensión de archivo comprimido")
        return record
    if ext in extensions.get("images", []):
        record.kind, record.family = "image", "Images"
        return record
    if ext in extensions.get("documentation", []):
        record.kind, record.family = "documentation", "Documentation"
        return record
    audio = ext in extensions.get("audio", [])
    midi = ext in extensions.get("midi", [])
    if not audio and not midi:
        record.kind, record.family = "other", "Unknown files"
        record.reasons.append("Extensión no reconocida como audio o MIDI")
        return record

    dirs = list(path.relative_to(root).parts[:-1])
    family_markers = [(directory, marker) for directory in dirs if (marker := _family_marker(directory))]
    if midi:
        family = "MIDI"
        record.kind = "midi"
    elif _filename_family(name):
        family = _filename_family(name)
        record.kind = "audio"
    elif family_markers:
        family = family_markers[-1][1]
        record.kind = "audio"
    else:
        family = _infer_family(path, dirs, name, settings)
        record.kind = "audio"
        if not family:
            return _unclassified(record, "No hay señales suficientes para distinguir loop de one-shot")

    category = _category(family, dirs[1:], name, settings)
    if not category:
        return _unclassified(record, "No se encontró una categoría suficientemente clara", family)
    record.family = family
    record.category = category
    evidence = _evidence(family, dirs, name)
    record.reasons.extend(evidence)
    record.confidence = "high" if family_markers or midi else "medium"
    if library_confidence == "low":
        record.confidence = "low"
    if not family_markers and not midi:
        record.reasons.append("Familia inferida mediante nombre/ruta, sin carpeta explícita")
    return record


def _infer_family(path: Path, dirs: list[str], name: str, config: dict) -> str:
    if re.search(r"\b\d{2,3}\s*bpm\b", normalize(name)):
        return "Loops"
    aliases = config.get("aliases", {})
    instruments = ("Kick", "Snare", "Clap", "Rim", "Tom", "HiHat", "HiHat Closed", "HiHat Open",
                   "Cymbal", "Percussion", "Bass", "808", "FX", "Texture", "Guitar", "Keys")
    if any(_matches(" ".join(dirs[1:] + [name]), a) for key in instruments for a in aliases.get(key, [])):
        return "One Shots"
    return ""


def _category(family: str, dirs: list[str], filename: str, config: dict) -> str:
    aliases = config.get("aliases", {})
    priorities = {"HiHat Closed": 4, "HiHat Open": 4, "HiHat": 1, "Drums": 0,
                  "Percussion": 1, "Melody": 0, "Kick": 2, "Snare": 2, "Clap": 2,
                  "Rim": 3, "Tom": 2, "Cymbal": 2, "Keys": 3, "808": 4, "Bass": 3}
    allowed = {
        "One Shots": ["Kick", "Snare", "Clap", "HiHat Closed", "HiHat Open", "HiHat", "Rim", "Tom", "Percussion", "Cymbal", "Bass", "808", "Synth", "Keys", "Guitar", "Vocal", "FX", "Foley", "Texture", "Brass", "Woodwind", "Strings", "Melody"],
        "Loops": ["Bass", "Drums", "Percussion", "Synth", "Keys", "Guitar", "Vocal", "FX", "Texture", "Melody", "Brass", "Woodwind", "Strings"],
        "MIDI": ["Bass", "Chords", "Melody", "Drums", "Arpeggio", "Keys", "Guitar", "Brass", "Synth", "Strings", "Woodwind"],
    }.get(family, [])
    # A filename or a nearby instrument folder is more reliable than a pack title.
    # Short aliases such as SD (Slate Digital) must not masquerade as snare.
    sources = [Path(filename).stem, *reversed(dirs)]
    if family == "Loops" and any(_matches(d, "drum loop") or _matches(d, "drum loops")
                                 for d in dirs):
        return "Drums"
    if family == "MIDI" and any(_matches(d, "progression") for d in dirs):
        return "Chords"
    best: tuple[int, int, str] | None = None
    for index, text in enumerate(sources):
        normalized_text = f" {normalize(text)} "
        hits = [category for category in allowed
                if any(f" {normalize(alias)} " in normalized_text for alias in aliases.get(category, [category])
                       if normalize(alias) != "sd")]
        if family == "Loops" and any(f" {alias} " in normalized_text for alias in
                                     ("kick", "snare", "clap", "hat", "hihat", "rim", "rimshot", "cymbal", "crash", "ride", "tom")):
            hits.append("Drums")
        if hits:
            hits.sort(key=lambda category: priorities.get(category, 2), reverse=True)
            if len(hits) > 1 and priorities.get(hits[0], 2) == priorities.get(hits[1], 2):
                continue
            candidate = (priorities.get(hits[0], 2), -index, hits[0])
            if best is None or candidate > best:
                best = candidate
    if best:
        return best[2]
    if family == "One Shots" and any(normalize(d) in {"drum", "drums", "drum kit"} for d in dirs):
        return "Drums/Other"
    if family == "MIDI" or any(normalize(d) == "other" for d in dirs):
        return "Other"
    return ""


def _evidence(family: str, dirs: list[str], filename: str) -> list[str]:
    reasons = []
    for directory in dirs:
        if _family_marker(directory) == family or (family == "MIDI" and normalize(directory) == "midi"):
            reasons.append(f'Carpeta "{directory}" indica {family}')
    for directory in dirs:
        if normalize(directory) in {"drum", "drums"}:
            reasons.append(f'Carpeta "{directory}" indica categoría de drums')
    reasons.append(f'Categoría inferida de ruta/nombre: {filename}')
    return reasons


def _unclassified(record: SampleRecord, reason: str, family: str = "") -> SampleRecord:
    record.family = "Unclassified"
    record.category = ""
    record.confidence = "low"
    record.reasons.append(reason)
    return record
