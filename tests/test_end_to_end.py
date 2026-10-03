import json
from pathlib import Path

from sample_organizer.organizer import organize
from sample_organizer.scanner import scan


def test_analyze_then_organize_keeps_sources_and_writes_complete_reports(tmp_path):
    source = tmp_path / "Samples"
    destination = tmp_path / "SamplesOrdenados"
    fixtures = {
        "Pack A/One Shots/Drums/Kicks/kick01.wav": b"kick sample",
        "Pack B/One Shots/Drums/Kicks/kick01.wav": b"kick sample",
        "Hiphop Collection/Loops/Bass/bass_90bpm.wav": b"bass loop",
        "Trap Pack/MIDI/Chords/chords01.mid": b"midi data",
        "Unclear Pack/Audio/mystery.wav": b"unknown audio",
        "Downloads/incomplete.wav.part": b"partial download",
        "Pack A/Lyrics/song.lrc": b"[00:01.00] lyrics",
        "Pack A/.DS_Store": b"finder metadata",
        "Pack A/._kick01.wav": b"apple double metadata",
        "Pack A/readme.pdf": b"documentation",
    }
    for relative, content in fixtures.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    analysis = scan(source, destination)
    assert not destination.exists(), "Analizar no debe crear ni modificar el destino"
    assert {r.relative_to(source).as_posix(): r.read_bytes() for r in source.rglob("*") if r.is_file()} == fixtures
    by_name = {record.filename: record for record in analysis.records if record.filename != "kick01.wav"}
    assert analysis.summary() == {
        "files_found": 10,
        "one_shots": 2,
        "loops": 1,
        "midi": 1,
        "unclassified": 1,
        "part": 1,
        "lrc": 1,
        "macos_metadata": 2,
        "pending_deletion": 4,
        "duplicates": 1,
        "other": 1,
        "archives": 0,
    }
    assert by_name["bass_90bpm.wav"].category == "Bass"
    assert by_name["chords01.mid"].category == "Chords"
    assert by_name["mystery.wav"].family == "Unclassified"

    outcome = organize(analysis, destination)
    assert outcome.copied == 5
    assert outcome.deleted_parts == 0
    assert (destination / "One Shots/Drums/Kick/Pack A/kick01.wav").read_bytes() == b"kick sample"
    assert (destination / "One Shots/Drums/Kick/Pack B/kick01.wav").read_bytes() == b"kick sample"
    assert (destination / "Loops/Bass/Hiphop Collection/bass_90bpm.wav").exists()
    assert (destination / "MIDI/Chords/Trap Pack/chords01.mid").exists()
    assert (destination / "Unclassified/Unclear Pack/mystery.wav").exists()
    assert (source / "Downloads/incomplete.wav.part").exists()
    assert (source / "Pack A/Lyrics/song.lrc").exists()
    assert not (destination / "Pack A/readme.pdf").exists()
    assert outcome.report_csv and outcome.report_csv.is_file()
    assert outcome.report_json and outcome.report_json.is_file()
    report = json.loads(outcome.report_json.read_text(encoding="utf-8"))
    assert len(report) == 10
    assert sum(entry["action"] == "copy" for entry in report) == 5
    assert sum(bool(entry["duplicate_of"]) for entry in report) == 1
    matching_hashes = [entry["duplicate_hash"] for entry in report if entry["duplicate_hash"]]
    assert len(matching_hashes) >= 2
