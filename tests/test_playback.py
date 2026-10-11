import numpy as np

from core.models import Note
from core.generator import generate
from core.patterns import TRACKS
from core.playback import SR, AudioEngine, click_buffer, mix, render_tracks

MELODY = [Note(64, 0, 1), Note(67, 4, 2), Note(69, 8, 1), Note(65, 12, 2)]


def song(bpm=100, genre="pop"):
    return generate(MELODY, 0, "major", bpm, genre)


def test_loop_length_exact_for_all_tempos():
    for bpm in (60, 100, 133, 160):
        tr = render_tracks(song(bpm))
        assert all(len(tr[t]) == round(16 * 60 / bpm * SR) for t in TRACKS)


def test_render_is_deterministic_and_bounded():
    a = mix(render_tracks(song()), "pop")
    b = mix(render_tracks(song()), "pop")
    assert np.array_equal(a, b) and np.isfinite(a).all() and np.abs(a).max() <= 1.0
    assert np.abs(a).max() > 0.1


def test_mute_changes_mix_and_all_muted_is_silent():
    tr = render_tracks(song(genre="lo-fi"))
    full = mix(tr, "lo-fi")
    assert not np.array_equal(full, mix(tr, "lo-fi", muted={"drums"}))
    assert np.abs(mix(tr, "lo-fi", muted=set(TRACKS))).max() == 0


def test_genres_sound_different():
    assert not np.array_equal(mix(render_tracks(song(genre="pop")), "pop"),
                              mix(render_tracks(song(genre="lo-fi")), "lo-fi"))


def _pull(engine, frames):
    out = np.zeros((frames, 1), dtype=np.float32)
    engine._callback(out, frames, None, None)
    return out[:, 0].copy()


def test_engine_loops_seamlessly_and_swaps_on_boundary():
    eng = AudioEngine()
    a = np.arange(1000, dtype=np.float32)
    b = -np.arange(1, 801, dtype=np.float32)
    eng.set_loop(a)
    eng.play()
    got = np.concatenate([_pull(eng, 512) for _ in range(4)])   # 2048 samples
    assert np.array_equal(got[:1000], a)
    assert np.array_equal(got[1000:2000], a)                    # wrapped, no gap/drift
    eng.set_loop(b)                                             # while playing -> pending
    got = np.concatenate([_pull(eng, 512) for _ in range(3)])
    # position was 48 into loop `a`; swap happens at its end (index 952)
    assert np.array_equal(got[:952], a[48:])
    assert np.array_equal(got[952:952 + 584], b[:584])


def test_engine_stopped_is_silent_and_oneshot_calls_back():
    eng = AudioEngine()
    eng.set_loop(np.ones(100, dtype=np.float32))
    assert not _pull(eng, 64).any()
    done = []
    eng.play_oneshot(click_buffer(120, beats=1), lambda: done.append(1))
    n = len(click_buffer(120, beats=1))
    for _ in range(n // 512 + 1):
        _pull(eng, 512)
    assert done == [1]


def test_engine_callback_fills_every_output_channel():
    eng = AudioEngine()
    a = np.arange(1, 101, dtype=np.float32)
    eng.set_loop(a); eng.play()
    out = np.zeros((64, 2), dtype=np.float32)
    eng._callback(out, 64, None, None)
    assert np.array_equal(out[:, 0], a[:64]) and np.array_equal(out[:, 1], a[:64])
