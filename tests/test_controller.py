import os
import tempfile
import time
import wave

from core.controller import Controller

states = []


def make():
    states.clear()
    return Controller(on_state=lambda s, i: states.append((s, i)))


def test_demo_flow_and_live_settings_change():
    c = make()
    c.load_demo()
    assert c.song is not None and c.key_text() == "Key: C major"
    assert c.chords_text() == "C  G  Am  F"
    melody_before = list(c.song.melody)

    c.genre = "lo-fi"; c._rebuild()                    # genre change: no re-record needed
    assert c.song.genre == "lo-fi" and c.song.melody == melody_before
    c.bpm = 140; c._rebuild()
    assert c.song.bpm == 140
    c.key_override = (9, "minor"); c._rebuild()        # manual key (FR-14)
    assert c.key_text() == "Key: A minor (manual)"
    assert all(n.midi % 12 in {9, 11, 0, 2, 4, 5, 7} for n in c.song.melody)


def test_processing_time_under_2s():
    c = make()
    t0 = time.perf_counter()
    c.load_demo()
    c.genre = "lo-fi"; c.bpm = 60; c._rebuild()        # slowest case: longest loop
    assert time.perf_counter() - t0 < 2.0


def test_empty_recording_is_friendly_error_not_crash():
    c = make()
    assert c.process_notes([]) is False
    assert states[-1][0] == "error" and "No notes" in states[-1][1]["message"]


def test_save_wav_and_mute():
    c = make()
    c.load_demo()
    c.set_track_enabled("drums", False)
    assert "drums" in c.muted
    path = os.path.join(tempfile.mkdtemp(), "out.wav")
    assert c.save_wav(path)
    with wave.open(path) as w:
        assert w.getframerate() == 44100 and w.getnframes() > 44100 * 5


def test_missing_mic_reports_error():
    c = make()
    c.recorder.start = lambda *a: (_ for _ in ()).throw(__import__("core.audio_in").audio_in.MicError("none"))
    c.record()
    assert states[-1][0] == "error"


# ------------------------------------------------------------- melody editing
def _wait_built(c, timeout=5.0):
    t0 = time.perf_counter()
    while c.built_rev != c.edit_rev and time.perf_counter() - t0 < timeout:
        time.sleep(0.01)
    assert c.built_rev == c.edit_rev


def test_edit_melody_rebuilds_band_and_undo_redo():
    from core.models import Note
    c = make()
    c.load_demo()
    original = [(n.midi, n.start, n.duration) for n in c.song.melody]
    # move the whole phrase up a scale step (C major -> D..), and drop the last note
    edited = [Note(62 if n.midi == 60 else n.midi, n.start, n.duration) for n in c.song.melody[:-1]]
    rev = c.set_melody(edited)
    assert rev == c.edit_rev and c.can_undo and not c.can_redo
    _wait_built(c)
    assert len(c.song.melody) == len(original) - 1 and c.song.melody[0].midi == 64
    assert c.song.bpm == 100 and len(c.song.chords) > 0        # band still generated

    c.undo(); _wait_built(c)
    assert [(n.midi, n.start, n.duration) for n in c.song.melody] == original and c.can_redo
    c.redo(); _wait_built(c)
    assert len(c.song.melody) == len(original) - 1


def test_edit_is_clamped_and_empty_melody_is_allowed():
    from core.models import Note
    c = make()
    c.load_demo()
    c.set_melody([Note(60, -3.0, 2.0), Note(64, 15.5, 4.0), Note(67, 2.0, 0.0)])
    _wait_built(c)
    mel = c.song.melody
    assert [n.start for n in mel] == [0.0, 15.5] and mel[1].end == 16.0   # clamped, zero-length dropped
    c.set_melody([]); _wait_built(c)
    assert c.song.melody == [] and len(c.song.chords) > 0 and c.chords_text()


def test_rerecording_or_demo_is_undoable_and_edit_ignored_while_busy():
    from core.models import Note
    c = make()
    assert c.set_melody([Note(60, 0, 1)]) is None and c.undo() is None   # nothing recorded yet
    c.load_demo()
    gen = c.melody_gen
    c.set_melody([Note(67, 0, 4)]); _wait_built(c)
    c.load_demo(); _wait_built(c)                          # "re-hum": new recognition result
    assert c.melody_gen == gen + 1 and len(c.song.melody) == 15
    c.undo(); _wait_built(c)                               # back to the edited single note
    assert [n.midi for n in c.song.melody] == [67]
    c.state = "recording"
    assert c.set_melody([Note(60, 0, 1)]) is None and c.undo() is None


def test_snap_to_key_off_keeps_out_of_scale_notes_and_on_snaps_them_back():
    from core.models import Note
    c = make()
    c.load_demo()
    c.set_scale_lock(False)
    c.set_melody([Note(61, 0, 1), Note(66, 2, 1)]); _wait_built(c)      # C# and F# in C major
    assert [n.midi for n in c.song.melody] == [61, 66]
    c.set_scale_lock(True); time.sleep(0.3)
    assert all(n.midi % 12 in {0, 2, 4, 5, 7, 9, 11} for n in c.song.melody)
    # switching it off must not move what the user sees
    shown = [n.midi for n in c.song.melody]
    c.set_scale_lock(False); time.sleep(0.3)
    assert [n.midi for n in c.song.melody] == shown


def test_auto_key_redetects_from_edited_melody():
    from core.models import Note
    c = make()
    c.load_demo()
    assert c.key_text() == "Key: C major"
    c.set_melody([Note(m, i, 1) for i, m in enumerate([69, 71, 72, 74, 76, 74, 72, 69])]); _wait_built(c)
    c.set_key_override((7, "major")); time.sleep(0.2)
    c.set_key_override(None); time.sleep(0.3)
    assert c.key_override is None and c.detected_key == (9, "minor")   # A..A phrase, not the old C major
