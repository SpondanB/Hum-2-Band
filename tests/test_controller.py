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
