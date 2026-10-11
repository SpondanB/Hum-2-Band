import numpy as np

from core.audio_in import MicRecorder, level_from_rms
from core.analysis import frames_to_notes
from core.pitch import SR


def tone(freq, secs, amp=0.3):
    t = np.arange(int(secs * SR)) / SR
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_recorder_pipeline_without_hardware():
    """Synthetic hum through the same code path the mic uses."""
    done = []
    rec = MicRecorder(on_capture_done=done.append)
    rec.begin_capture  # API exists
    rec._capturing, rec._t0, rec._duration, rec._frames = True, 0.0, 2.0, []
    audio = np.concatenate([tone(220, 1.0), np.zeros(int(0.2 * SR), np.float32),
                            tone(261.63, 1.0)])
    rec.feed(audio)
    assert len(done) == 1
    notes = frames_to_notes(done[0], bpm=120)
    assert [n.midi for n in notes][:2] == [57, 60]           # A3, C4


def test_silence_yields_no_voiced_frames():
    done = []
    rec = MicRecorder(on_capture_done=done.append)
    rec._capturing, rec._t0, rec._duration, rec._frames = True, 0.0, 1.0, []
    rec.feed(np.zeros(SR + 2048, np.float32))
    assert done and all(f.midi is None for f in done[0])
    assert frames_to_notes(done[0], 120) == []


def test_level_meter_range():
    assert level_from_rms(0) == 0.0 and level_from_rms(1.0) == 1.0
    assert 0 < level_from_rms(0.01) < 1
