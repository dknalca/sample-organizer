from pathlib import Path
import pytest

from sample_organizer.cancellation import CancellationToken, TaskCancelled
from sample_organizer.scanner import scan


def test_scans_and_detects_exact_duplicates(tmp_path):
    source = tmp_path / "Samples"
    source.mkdir()
    first = source / "Pack" / "One Shots" / "Drums" / "Kick" / "kick.wav"
    second = source / "Pack" / "One Shots" / "Drums" / "Kick" / "kick-copy.wav"
    first.parent.mkdir(parents=True)
    first.write_bytes(b"same audio bytes")
    second.write_bytes(b"same audio bytes")
    (source / "Pack" / "unfinished.part").write_bytes(b"partial")

    progress = []
    result = scan(source, progress=lambda count, message: progress.append(message))
    assert len(result.records) == 3
    duplicate = next(record for record in result.records if record.filename == "kick-copy.wav")
    assert duplicate.duplicate_of
    assert duplicate.duplicate_hash
    assert result.summary()["part"] == 1
    assert any(message.startswith("Escaneando archivos") for message in progress)
    assert any(message.startswith("Comparando duplicados") for message in progress)
    assert any(message.startswith("Calculando hash") for message in progress)
    assert progress[-1].startswith("Análisis finalizado")


def test_destination_inside_source_is_rejected(tmp_path):
    source = tmp_path / "Samples"
    source.mkdir()
    try:
        scan(source, source / "Organized")
    except ValueError as exc:
        assert "dentro" in str(exc)
    else:
        raise AssertionError("expected destination validation")


def test_scan_can_be_cancelled_without_mutating_source(tmp_path):
    source = tmp_path / "Samples"
    source.mkdir()
    sample = source / "Pack" / "One Shots" / "Drums" / "Kick" / "kick.wav"
    sample.parent.mkdir(parents=True)
    sample.write_bytes(b"unchanged")
    token = CancellationToken()

    def request_stop(count, message):
        if message.startswith("Analizando directorio:"):
            token.cancel()

    with pytest.raises(TaskCancelled):
        scan(source, progress=request_stop, cancellation=token)
    assert sample.read_bytes() == b"unchanged"
