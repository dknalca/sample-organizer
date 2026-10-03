import csv
from pathlib import Path
from sample_organizer.cancellation import CancellationToken

from sample_organizer.models import ScanResult
from sample_organizer.organizer import destination_for, organize
from sample_organizer.scanner import scan


def test_copy_collision_keeps_both_and_writes_reports(tmp_path):
    source = tmp_path / "Samples"
    destination = tmp_path / "Organized"
    for pack in ("Pack A", "Pack B"):
        item = source / pack / "One Shots" / "Drums" / "Kick" / "kick.wav"
        item.parent.mkdir(parents=True)
        item.write_bytes(pack.encode())
    result = scan(source, destination)
    organized = organize(result, destination)
    assert organized.copied == 2
    assert organized.report_csv and organized.report_csv.exists()
    assert organized.report_json and organized.report_json.exists()
    assert all(record.action == "copy" for record in result.records)
    assert all((destination_for(record)) for record in result.records)
    with organized.report_csv.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2
    assert all(row["original_path"] and row["classification_reason"] for row in rows)


def test_existing_destination_file_is_not_overwritten(tmp_path):
    source = tmp_path / "Samples"
    destination = tmp_path / "Organized"
    original = source / "Pack" / "One Shots" / "Drums" / "Kick" / "kick.wav"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"new source")
    expected = destination / "One Shots" / "Drums" / "Kick" / "Pack" / "kick.wav"
    expected.parent.mkdir(parents=True)
    expected.write_bytes(b"existing")
    result = scan(source, destination)
    outcome = organize(result, destination)
    assert outcome.copied == 1
    assert expected.read_bytes() == b"existing"
    assert result.records[0].renamed_due_to_collision
    assert Path(result.records[0].destination_path).name == "kick_2.wav"


def test_part_is_preserved_without_explicit_delete(tmp_path):
    source = tmp_path / "Samples"
    destination = tmp_path / "Organized"
    source.mkdir()
    part = source / "unfinished.wav.part"
    part.write_bytes(b"unfinished")
    result = scan(source, destination)
    organize(result, destination)
    assert part.exists()
    assert result.records[0].action == "skip"


def test_part_deleted_only_when_explicitly_requested(tmp_path):
    source = tmp_path / "Samples"
    destination = tmp_path / "Organized"
    source.mkdir()
    part = source / "unfinished.wav.part"
    part.write_bytes(b"unfinished")
    result = scan(source, destination)
    outcome = organize(result, destination, delete_pending=True)
    assert outcome.deleted_parts == 1
    assert not part.exists()


def test_lrc_is_preserved_by_default_and_deleted_only_when_requested(tmp_path):
    source = tmp_path / "Samples"
    destination = tmp_path / "Organized"
    source.mkdir()
    lyrics = source / "Pack" / "Lyrics" / "song.lrc"
    lyrics.parent.mkdir(parents=True)
    lyrics.write_text("[00:01.00] lyrics", encoding="utf-8")

    result = scan(source, destination)
    assert result.summary()["lrc"] == 1
    assert result.records[0].is_pending_deletion
    organize(result, destination)
    assert lyrics.exists()
    assert result.records[0].action == "skip"

    result = scan(source, destination)
    outcome = organize(result, destination, delete_pending=True)
    assert outcome.deleted_lrc == 1
    assert not lyrics.exists()
    assert result.records[0].action == "delete_lrc"


def test_macos_metadata_files_are_preserved_unless_cleanup_is_confirmed(tmp_path):
    source = tmp_path / "Samples"
    destination = tmp_path / "Organized"
    source.mkdir()
    ds_store = source / "Pack" / ".DS_Store"
    apple_double = source / "Pack" / "._kick.wav"
    ds_store.parent.mkdir(parents=True)
    ds_store.write_bytes(b"finder metadata")
    apple_double.write_bytes(b"apple double metadata")

    result = scan(source, destination)
    assert result.summary()["macos_metadata"] == 2
    organize(result, destination)
    assert ds_store.exists() and apple_double.exists()

    result = scan(source, destination)
    outcome = organize(result, destination, delete_pending=True)
    assert outcome.deleted_macos_metadata == 2
    assert not ds_store.exists() and not apple_double.exists()
    assert {record.action for record in result.records} == {"delete_macos_metadata"}


def test_non_musical_files_are_not_copied(tmp_path):
    source = tmp_path / "Samples"
    destination = tmp_path / "Organized"
    source.mkdir()
    (source / "readme.pdf").write_bytes(b"documentation")
    result = scan(source, destination)
    outcome = organize(result, destination)
    assert outcome.copied == 0
    assert not (destination / "readme.pdf").exists()
    assert result.records[0].action == "skip"


def test_destination_symlink_is_not_followed(tmp_path):
    source = tmp_path / "Samples"
    destination = tmp_path / "Organized"
    outside = tmp_path / "Outside"
    outside.mkdir()
    original = source / "Pack" / "One Shots" / "Drums" / "Kick" / "kick.wav"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"audio")
    destination.mkdir()
    (destination / "One Shots").symlink_to(outside, target_is_directory=True)
    result = scan(source, destination)
    outcome = organize(result, destination)
    assert outcome.copied == 0
    assert outcome.errors
    assert not list(outside.iterdir())


def test_stop_organization_keeps_completed_copies_and_writes_report(tmp_path):
    source = tmp_path / "Samples"
    destination = tmp_path / "Organized"
    for pack in ("Pack A", "Pack B"):
        audio = source / pack / "One Shots" / "Drums" / "Kick" / "kick.wav"
        audio.parent.mkdir(parents=True)
        audio.write_bytes(pack.encode())
    result = scan(source, destination)
    token = CancellationToken()

    def stop_after_first(count, message):
        if count == 1:
            token.cancel()

    outcome = organize(result, destination, cancellation=token, progress=stop_after_first)
    assert outcome.cancelled
    assert outcome.copied == 1
    assert outcome.report_json and outcome.report_json.exists()
    assert sum(record.action == "copy" for record in result.records) == 1
    assert sum(record.action == "cancelled" for record in result.records) == 1
