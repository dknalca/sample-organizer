from pathlib import Path

from sample_organizer.classifier import classify, detect_library, normalize


def result(path: str):
    source = Path("/Samples")
    return classify(Path(path), source)


def test_one_shot_expected_classification():
    item = result("/Samples/Pack A/One Shots/Drums/Kicks/kick01.wav")
    assert (item.family, item.category, item.library) == ("One Shots", "Kick", "Pack A")
    assert item.confidence == "high"
    assert item.reasons


def test_loop_expected_classification():
    item = result("/Samples/Hiphop Collection/Loops/Bass/bass_90bpm.wav")
    assert (item.family, item.category, item.library) == ("Loops", "Bass", "Hiphop Collection")


def test_midi_expected_classification():
    item = result("/Samples/Trap Pack/MIDI/Chords/chords01.mid")
    assert (item.family, item.category, item.library) == ("MIDI", "Chords", "Trap Pack")


def test_normalizes_case_underscores_hyphens_and_unicode():
    assert normalize("CLOSED_HAT") == normalize("Closed-Hat") == normalize("closed hat")
    item = result("/Samples/Paquete Ñ/One-Shots/Drums/CLOSED_HAT/uno.WAV")
    assert item.family == "One Shots"
    assert item.category == "HiHat Closed"
    assert item.library == "Paquete Ñ"


def test_generic_folders_are_not_library_names():
    library, _, _ = detect_library(Path("/Samples/Vendor/Soul Sessions Vol 2/Loops/Bass/x.wav"), Path("/Samples"))
    assert library == "Soul Sessions Vol 2"


def test_ambiguous_audio_is_unclassified():
    item = result("/Samples/Pack/Audio/file.wav")
    assert item.family == "Unclassified"
    assert item.confidence == "low"


def test_explicit_loop_filename_overrides_one_shots_directory():
    item = result("/Samples/Pack/One Shots/Kick/long_loop.wav")
    assert (item.family, item.category) == ("Loops", "Drums")


def test_real_pack_folder_markers_and_slate_prefix():
    kick = result("/Samples/SamplePack by Slate Digital/SD_SEISMIC_DrumSamplePack/One Shots/Kick/SD_SEISMIC_kick_pluto.wav")
    assert (kick.family, kick.category) == ("One Shots", "Kick")
    hat = result("/Samples/Pack/Drums/Drum One Shots/Hat/Closed Hat/SD_CAICOS_hat_snack.wav")
    assert (hat.family, hat.category) == ("One Shots", "HiHat Closed")
    assert result("/Samples/Maxeyy Drum Kit/Cymbals/Ride - Nine.wav").category == "Cymbal"


def test_drum_stems_remain_loops_despite_kick_or_snare_names():
    for path, category in (
        ("/Samples/Pack/Drum Loops/Loop Stems/Song/Cymatics - Song Drum Loop - 120 BPM Kick.wav", "Drums"),
        ("/Samples/Pack/Kit_01/_(WAVs)_Loops/ihb_kit01_snare_102bpm.wav", "Drums"),
        ("/Samples/Pack/Drum One Shots/Percussion/SD_EMPRESS_perc_ShakerLoop.wav", "Percussion"),
    ):
        item = result(path)
        assert (item.family, item.category) == ("Loops", category)


def test_midi_progressions_and_instrument_names():
    chords = result("/Samples/Pack/MIDI/Slate Digital EDM Signature Progressions/SD_EDM_49_124_Gm.mid")
    guitar = result("/Samples/Pack/Kit_01/_(MIDIs)_Files/ihb_kit01_guitar_102bpm.mid")
    brass = result("/Samples/Pack/Kit_01/_(MIDIs)_Files/ihb_kit01_brass_102bpm.mid")
    assert (chords.family, chords.category) == ("MIDI", "Chords")
    assert (guitar.family, guitar.category) == ("MIDI", "Guitar")
    assert (brass.family, brass.category) == ("MIDI", "Brass")
    assert result("/Samples/Pack/MIDI/mystery.mid").family == "MIDI"


def test_tonal_808_samples_and_unknown_clips():
    item = result("/Samples/Pack/Tonal/808/SD_CAICOS_808_stub_B.wav")
    assert (item.family, item.category) == ("One Shots", "808")
    assert result("/Samples/Pack/Sound Clip Stash/Last sunset.wav").family == "Unclassified"
    assert result("/Samples/Pack/16.wav").family == "Unclassified"


def test_snare_rim_is_rim_as_requested():
    item = result("/Samples/JAKE REED SUPER DEAD DRUMS VOL  2/SDD VOL 2 ONE SHOTS/SDD 2 SNARE RIM/SDD 2 SNARE RIM V1/JR_SDD2_SNARE_RIM_V1_a.wav")
    assert (item.family, item.category) == ("One Shots", "Rim")


def test_part_is_only_marked_pending():
    item = result("/Samples/Pack/audio.wav.part")
    assert item.is_part
    assert item.kind == "part"
    assert "pendiente" in " ".join(item.reasons)


def test_lrc_is_marked_pending_for_explicit_cleanup():
    item = result("/Samples/Pack A/Lyrics/song.lrc")
    assert item.is_lrc
    assert item.is_pending_deletion
    assert item.kind == "lrc"
    assert item.family == "Pending deletion"
    assert ".lrc" in " ".join(item.reasons)


def test_macos_generated_files_are_pending_cleanup():
    for filename in (".DS_Store", "._kick01.wav", ".apdisk", ".LSOverride", ".localized"):
        item = result(f"/Samples/Pack A/{filename}")
        assert item.is_macos_metadata
        assert item.is_pending_deletion
        assert item.kind == "macos_metadata"


def test_archive_is_informational():
    item = result("/Samples/Pack/samples.ZIP")
    assert item.kind == "archive"
    assert item.family == "Archives"
