"""Rule-based chord and bass generation. No Kivy imports."""
from .models import Note, Song
from .patterns import NOTE_NAMES, PREFERRED_PROGRESSION, SCALES


def scale_pcs(root, mode):
    return [(root + i) % 12 for i in SCALES[mode]]


def diatonic_chords(root, mode):
    """Triads on degrees I..vi as [root_pc, third_pc, fifth_pc]."""
    sc = scale_pcs(root, mode)
    return [[sc[d], sc[(d + 2) % 7], sc[(d + 4) % 7]] for d in range(6)]


def _overlap(n, b0, b1):
    return max(0.0, min(n.end, b1) - max(n.start, b0))


def choose_chords(melody, root, mode, bars=4):
    """Return one degree index (0..5) per bar with longer-phrase variation."""
    chords = diatonic_chords(root, mode)
    pref = PREFERRED_PROGRESSION[mode]
    phrase_bank = {
        "major": [0, 4, 5, 3, 0, 1, 4, 5, 0, 5, 4, 3, 0, 2, 4, 5],
        "minor": [0, 5, 3, 4, 0, 1, 5, 3, 0, 4, 5, 3, 0, 2, 5, 4],
    }
    phrase = phrase_bank[mode]
    choice = []
    for bar in range(bars):
        b0, b1 = bar * 4, bar * 4 + 4
        scores = [sum(_overlap(n, b0, b1) for n in melody if n.midi % 12 in pcs)
                  for pcs in chords]
        best = max(scores)
        tied = [d for d, s in enumerate(scores) if abs(s - best) < 1e-9]
        if not tied:
            tied = [0]
        target = phrase[bar % len(phrase)]
        if len(tied) == 1:
            pick = tied[0]
        elif target in tied:
            pick = target
        elif pref[bar % len(pref)] in tied:
            pick = pref[bar % len(pref)]
        else:
            pick = sorted(tied, key=lambda d: (d not in (0, 3, 4), d))[0]
        choice.append(pick)
    return choice


def voice_chord(pcs, base=48):
    """Stack pitch classes upward starting with the root in [base, base+12)."""
    root = base + (pcs[0] - base) % 12
    notes = [root]
    for pc in pcs[1:]:
        prev = notes[-1]
        notes.append(prev + 1 + (pc - prev - 1) % 12)
    return notes


def generate(melody, root, mode, bpm, genre, bars=4, duration_beats=None,
             bass_style="auto", drum_style="auto"):
    duration_beats = float(duration_beats if duration_beats is not None else bars * 4)
    melody = [Note(note.midi, max(0.0, note.start),
                   min(note.end, duration_beats) - max(0.0, note.start))
              for note in melody if note.start < duration_beats and note.end > 0]
    chords_pcs = diatonic_chords(root, mode)
    sc = scale_pcs(root, mode)
    degrees = choose_chords(melody, root, mode, bars)

    chord_notes, bass_notes = [], []
    for bar, deg in enumerate(degrees):
        pcs = list(chords_pcs[deg])
        if genre == "lo-fi":
            pcs.append(sc[(deg + 6) % 7])   # add the 7th for a jazzier colour
        voiced = voice_chord(pcs)
        start = bar * 4.0
        chord_duration = min(4.0, max(0.0, duration_beats - start))
        if chord_duration:
            chord_notes += [Note(m, start, chord_duration) for m in voiced]

        bass_root = voiced[0] - 12
        if bass_style == "auto" and bars <= 4:
            if genre == "lo-fi":
                bass_line = [(0.0, 1.5), (2.0, 1.5)]
            else:
                bass_line = [(0.0, 3.5)]
            bass_events = [(beat, bass_root, length) for beat, length in bass_line]
        elif bass_style == "auto":
            if genre == "lo-fi":
                bass_line = [
                    (0.0, bass_root),
                    (1.0, bass_root + 7),
                    (2.0, bass_root),
                    (3.0, bass_root + 5),
                ]
            else:
                bass_line = [
                    (0.0, bass_root),
                    (1.5, bass_root + 7),
                    (2.5, bass_root),
                    (3.5, bass_root + 5),
                ]
            bass_events = [(beat, midi, 0.75 if genre == "lo-fi" else 0.5)
                           for beat, midi in bass_line]
        else:
            third, fifth = voiced[1] - 12, voiced[2] - 12
            bass_events = {
                "root_pulse": [(0.0, bass_root, 1.75), (2.0, bass_root, 1.75)],
                "root_fifth": [(0.0, bass_root, 0.8), (1.5, fifth, 0.45),
                               (2.0, bass_root, 0.8), (3.5, fifth, 0.45)],
                "walking": [(0.0, bass_root, 0.8), (1.0, third, 0.8),
                            (2.0, fifth, 0.8), (3.0, third, 0.8)],
                "syncopated": [(0.0, bass_root, 0.65), (1.5, fifth, 0.4),
                               (2.5, bass_root + 12, 0.65), (3.5, fifth, 0.4)],
            }.get(bass_style, [(0.0, bass_root, 3.5)])
        for beat, midi, length in bass_events:
            note_start = start + beat
            if note_start < duration_beats:
                bass_notes.append(Note(midi, note_start,
                                       min(length, duration_beats - note_start)))

    return Song(key_root=root, mode=mode, bpm=bpm, bars=bars, melody=list(melody),
                chords=chord_notes, bass=bass_notes, genre=genre,
                duration_beats=duration_beats, bass_style=bass_style,
                drum_style=drum_style)


def chord_labels(song):
    """Human-readable chord names, one per bar (e.g. ['C', 'G', 'Am', 'F'])."""
    labels = []
    for bar in range(song.bars):
        ns = sorted(n.midi for n in song.chords if n.start == bar * 4.0)
        if not ns:
            labels.append("-")
            continue
        root = ns[0]
        ivs = {(m - root) % 12 for m in ns}
        suffix = "dim" if {3, 6} <= ivs else ("m" if 3 in ivs else "")
        labels.append(NOTE_NAMES[root % 12] + suffix)
    return labels
