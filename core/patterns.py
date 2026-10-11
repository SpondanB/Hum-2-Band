"""Scales, genre drum tables, progressions and mix settings."""

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],   # natural minor
}

GENRES = ("pop", "lo-fi")
GENRE_LABELS = {"Pop": "pop", "Lo-fi": "lo-fi"}

# Preferred scale-degree progression (0-based degrees: 0=I, 3=IV, 4=V, 5=vi)
PREFERRED_PROGRESSION = {
    "major": [0, 4, 5, 3],   # I - V - vi - IV
    "minor": [0, 5, 3, 4],   # i - VI - iv - v
}

# 16-step grids (16th notes) per bar. Values are velocities (0..1).
DRUMS = {
    "pop": {
        "kick":  [1, 0, 0, 0,  0, 0, 0, 0,  1, 0, 0, 1,  0, 0, 0, 0],
        "snare": [0, 0, 0, 0,  1, 0, 0, 0,  0, 0, 0, 0,  1, 0, 0, 0],
        "hat":   [1, 0, 1, 0,  1, 0, 1, 0,  1, 0, 1, 0,  1, 0, 1, 0],
    },
    "lo-fi": {
        "kick":  [1, 0, 0, 0,  0, 0, 0, 1,  0, 0, 1, 0,  0, 0, 0, 0],
        "snare": [0, 0, 0, 0,  0.9, 0, 0, 0,  0, 0, 0, 0,  0.9, 0, 0, 0],
        "hat":   [0.6, 0, 0.3, 0.3,  0.6, 0, 0.3, 0,
                  0.6, 0, 0.3, 0.3,  0.6, 0, 0.3, 0.4],
    },
}

TRACKS = ("melody", "chords", "bass", "drums")
TRACK_GAINS = {"melody": 0.35, "chords": 0.20, "bass": 0.32, "drums": 0.50}
