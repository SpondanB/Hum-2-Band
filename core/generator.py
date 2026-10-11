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
    """Return one degree index (0..5) per bar."""
    chords = diatonic_chords(root, mode)
    pref = PREFERRED_PROGRESSION[mode]
    choice = []
    for bar in range(bars):
        b0, b1 = bar * 4, bar * 4 + 4
        scores = [sum(_overlap(n, b0, b1) for n in melody if n.midi % 12 in pcs)
                  for pcs in chords]
        best = max(scores)
        tied = [d for d, s in enumerate(scores) if abs(s - best) < 1e-9]
        if len(tied) == 1:
            pick = tied[0]
        elif pref[bar % 4] in tied:
            pick = pref[bar % 4]          # common progression breaks ties
        else:
            pick = sorted(tied, key=lambda d: (d not in (0, 3, 4), d))[0]  # I, IV, V first
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


def generate(melody, root, mode, bpm, genre, bars=4):
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
        chord_notes += [Note(m, start, 4.0) for m in voiced]
        bass_root = voiced[0] - 12           # one octave below the chord
        if genre == "lo-fi":
            bass_notes += [Note(bass_root, start, 1.5), Note(bass_root, start + 2, 1.5)]
        else:
            bass_notes.append(Note(bass_root, start, 3.5))

    return Song(key_root=root, mode=mode, bpm=bpm, bars=bars, melody=list(melody),
                chords=chord_notes, bass=bass_notes, genre=genre)


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
