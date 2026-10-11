import numpy as np

from core.analysis import (detect_key, freq_to_midi, frames_to_notes, midi_to_name,
                           quantize, quantize_pitch)
from core.models import Note, PitchFrame
from core.pitch import HOP, SR, YinDetector

HOP_S = HOP / SR


def seq(*items):
    """items: (midi_or_None, midi_seconds) -> list[PitchFrame] at hop spacing."""
    frames, i = [], 0
    for midi, dur in items:
        for _ in range(round(dur / HOP_S)):
            frames.append(PitchFrame(i * HOP_S, midi, 0.1, 0.95 if midi else 0.0))
            i += 1
    return frames


def notes_from(pairs):
    return [Note(m, float(i), 1.0) for i, m in enumerate(pairs)]


def test_freq_to_midi():
    assert round(freq_to_midi(440.0)) == 69
    assert round(freq_to_midi(261.63)) == 60
    assert midi_to_name(69) == "A4" and midi_to_name(60) == "C4"


def test_c_major_detected():
    assert detect_key(notes_from([60, 64, 67, 65, 64, 62, 60])) == (0, "major")


def test_a_minor_detected():
    assert detect_key(notes_from([69, 72, 76, 74, 72, 71, 69])) == (9, "minor")


def test_no_notes_returns_none():
    assert detect_key([]) is None


def test_out_of_scale_notes_snap_in():
    assert quantize_pitch(61, 0, "major") == 60      # tie -> down
    assert quantize_pitch(66, 0, "major") == 65
    assert quantize_pitch(64, 0, "major") == 64      # already in scale
    out = quantize([Note(61, 0, 1), Note(70, 1, 1)], 0, "major")
    assert all(n.midi % 12 in {0, 2, 4, 5, 7, 9, 11} for n in out)


def test_frames_to_notes_basic_and_grid():
    notes = frames_to_notes(seq((69, 1.0), (None, 0.3), (72, 0.5)), bpm=120)
    assert [n.midi for n in notes] == [69, 72]
    assert notes[0].start == 0.0 and notes[0].duration == 2.0
    assert all(n.start % 0.5 == 0 and n.duration % 0.5 == 0 for n in notes)


def test_short_blip_dropped():
    notes = frames_to_notes(seq((69, 1.0), (None, 0.1), (76, 0.05), (None, 0.1), (72, 0.5)), 120)
    assert [n.midi for n in notes] == [69, 72]


def test_octave_glitch_folded():
    frames = seq((69, 0.5))
    frames[20].midi = 81.0
    notes = frames_to_notes(frames, 120)
    assert len(notes) == 1 and notes[0].midi == 69


def test_silence_gives_no_notes():
    assert frames_to_notes(seq((None, 2.0)), 120) == []


def test_yin_detects_sine():
    det = YinDetector()
    t = np.arange(2048) / SR
    for f in (110.0, 220.0, 440.0, 660.0):
        freq, conf = det.detect(0.5 * np.sin(2 * np.pi * f * t))
        assert abs(freq - f) < 1.5, (f, freq)
        assert conf > 0.9
    assert det.detect(np.zeros(2048)) == (0.0, 0.0)
