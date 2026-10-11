from core.generator import chord_labels, choose_chords, diatonic_chords, generate, voice_chord
from core.models import Note


def test_diatonic_c_major():
    ch = diatonic_chords(0, "major")
    assert ch[0] == [0, 4, 7] and ch[3] == [5, 9, 0] and ch[5] == [9, 0, 4]


def test_chord_contains_most_melody_notes():
    melody = [Note(65, 0, 1), Note(69, 1, 1), Note(72, 2, 1)]   # F A C in bar 0
    deg = choose_chords(melody, 0, "major")[0]
    assert deg == 3                                              # IV = F A C


def test_empty_bars_follow_preferred_progression():
    assert choose_chords([], 0, "major") == [0, 4, 5, 3]         # I V vi IV


def test_ties_prefer_progression_not_repeats():
    melody = [Note(60, b * 4, 4) for b in range(4)]              # C held: I, IV, vi tie
    degs = choose_chords(melody, 0, "major")
    # bar 2: V isn't tied, so fall back to I/IV/V priority -> I; bars 3,4 use vi, IV
    assert degs == [0, 0, 5, 3]


def test_generate_structure_pop_and_lofi():
    melody = [Note(64, 0, 1), Note(67, 4, 1), Note(69, 8, 1), Note(65, 12, 1)]
    pop = generate(melody, 0, "major", 100, "pop")
    lofi = generate(melody, 0, "major", 100, "lo-fi")
    assert len(pop.chords) == 12 and len(lofi.chords) == 16     # lo-fi adds 7ths
    assert len(pop.bass) == 4 and len(lofi.bass) == 8           # beat 1 (+ beat 3)
    assert pop.melody == lofi.melody                             # genre never changes melody
    for song in (pop, lofi):
        labels = chord_labels(song)
        assert len(labels) == 4
        for bar in range(4):
            root = min(n.midi for n in song.chords if n.start == bar * 4)
            bass = [n.midi for n in song.bass if bar * 4 <= n.start < bar * 4 + 4]
            assert all(b == root - 12 for b in bass)             # root, octave below


def test_voicing_is_ascending_stack():
    v = voice_chord([9, 0, 4])
    assert v == sorted(v) and v[0] % 12 == 9 and 48 <= v[0] < 60


def test_minor_key_chords():
    ch = diatonic_chords(9, "minor")                             # A minor
    assert ch[0] == [9, 0, 4] and ch[5] == [5, 9, 0]             # Am, F
