"""Pitch frames -> notes, key detection, quantization. No Kivy imports."""
import math
import statistics

from .models import Note, PitchFrame
from .patterns import NOTE_NAMES, SCALES


def freq_to_midi(freq: float) -> float:
    return 69 + 12 * math.log2(freq / 440.0)


def midi_to_name(midi: float) -> str:
    m = int(round(midi))
    return f"{NOTE_NAMES[m % 12]}{m // 12 - 1}"


def _fold_octave_glitches(midis, radius=4):
    """Fix isolated octave-jump frames by comparing with neighbours' median."""
    out = list(midis)
    for i, m in enumerate(midis):
        if m is None:
            continue
        lo, hi = max(0, i - radius), min(len(midis), i + radius + 1)
        neigh = [midis[j] for j in range(lo, hi) if j != i and midis[j] is not None]
        if len(neigh) < 3:
            continue
        ref = statistics.median(neigh)
        d = m - ref
        if abs(abs(d) - 12) < 0.8:
            out[i] = m - 12 if d > 0 else m + 12
    return out


def _median_filter(midis, k=5):
    out = list(midis)
    half = k // 2
    for i, m in enumerate(midis):
        if m is None:
            continue
        win = [midis[j] for j in range(max(0, i - half), min(len(midis), i + half + 1))
               if midis[j] is not None]
        out[i] = statistics.median(win)
    return out


def _snap(x, grid):
    return math.floor(x / grid + 0.5) * grid


def frames_to_notes(frames, bpm, bars=4, hop_s=512 / 44100,
                    min_dur_s=0.1, grid=0.5):
    """Merge pitch frames into notes snapped to an 8th-note grid (grid=0.5 beat)."""
    total_beats = bars * 4
    beat_s = 60.0 / bpm

    midis = [f.midi for f in frames]
    midis = _median_filter(_fold_octave_glitches(midis), 5)

    groups, cur = [], None
    for f, m in zip(frames, midis):
        if m is None:
            continue
        if cur and f.t - cur["last"] <= 3 * hop_s and \
                abs(m - sum(cur["vals"]) / len(cur["vals"])) <= 0.5:
            cur["vals"].append(m)
            cur["last"] = f.t
        else:
            if cur:
                groups.append(cur)
            cur = {"first": f.t, "last": f.t, "vals": [m]}
    if cur:
        groups.append(cur)

    notes = []
    for g in groups:
        if g["last"] - g["first"] + hop_s < min_dur_s:
            continue
        midi = int(round(statistics.median(g["vals"])))
        s = _snap(g["first"] / beat_s, grid)
        e = _snap((g["last"] + hop_s) / beat_s, grid)
        s = min(max(s, 0.0), total_beats - grid)
        e = min(max(e, s + grid), total_beats)
        notes.append(Note(midi, s, e - s))

    # Keep the melody monophonic: trim overlaps, resolve identical starts.
    notes.sort(key=lambda n: n.start)
    result = []
    for n in notes:
        if result and n.start < result[-1].end:
            prev = result[-1]
            if n.start == prev.start:
                if n.duration > prev.duration:
                    result[-1] = n
                continue
            prev.duration = n.start - prev.start
        result.append(n)
    return result


def _scale_pcs(root, mode):
    return {(root + i) % 12 for i in SCALES[mode]}


def detect_key(notes):
    """Return (root, mode) for the best of 24 keys, or None if there are no notes."""
    if not notes:
        return None
    total = sum(n.duration for n in notes)
    ordered = sorted(notes, key=lambda n: n.start)
    first, last = ordered[0].midi % 12, ordered[-1].midi % 12
    best, best_score = None, -1.0
    for root in range(12):
        for mode in ("major", "minor"):
            pcs = _scale_pcs(root, mode)
            score = sum(n.duration for n in notes if n.midi % 12 in pcs)
            score += 0.1 * total * ((first == root) + (last == root))
            if score > best_score + 1e-9:
                best, best_score = (root, mode), score
    return best


def quantize_pitch(midi, root, mode):
    """Nearest in-scale pitch; prefer moving down on ties."""
    pcs = _scale_pcs(root, mode)
    for d in range(0, 7):
        if (midi - d) % 12 in pcs:
            return midi - d
        if (midi + d) % 12 in pcs:
            return midi + d
    return midi


def quantize(notes, root, mode):
    return [Note(quantize_pitch(n.midi, root, mode), n.start, n.duration) for n in notes]
