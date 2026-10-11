"""Scales, genre drum tables, progressions and mix settings."""

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],   # natural minor
}

GENRES = ("pop", "lo-fi", "rock", "funk", "hip-hop", "electronic")
GENRE_LABELS = {
    "Pop": "pop",
    "Lo-fi": "lo-fi",
    "Rock": "rock",
    "Funk": "funk",
    "Hip-hop": "hip-hop",
    "Electronic": "electronic",
}
BASS_STYLE_OPTIONS = {
    "Bass: Auto": "auto",
    "Bass: Root pulse": "root_pulse",
    "Bass: Root + fifth": "root_fifth",
    "Bass: Walking": "walking",
    "Bass: Syncopated": "syncopated",
}
DRUM_STYLE_OPTIONS = {
    "Drums: Auto": "auto",
    "Drums: Straight rock": "straight_rock",
    "Drums: Four-on-floor": "four_on_floor",
    "Drums: Half-time": "half_time",
    "Drums: Breakbeat": "breakbeat",
}
BASS_STYLES = tuple(BASS_STYLE_OPTIONS.values())
DRUM_STYLES = tuple(DRUM_STYLE_OPTIONS.values())

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
    "rock": {
        "kick":  [1, 0, 0, 0,  0, 0, 0, 0,  0.9, 0, 0.25, 0,  0, 0, 0, 0],
        "snare": [0, 0, 0, 0,  1, 0, 0, 0,  0, 0, 0, 0,  1, 0, 0, 0],
        "hat":   [0.65, 0, 0.45, 0,  0.65, 0, 0.45, 0,
                  0.65, 0, 0.45, 0,  0.65, 0, 0.45, 0],
    },
    "funk": {
        "kick":  [1, 0, 0, 0.25,  0, 0.45, 0, 0,  0.8, 0, 0, 0.35,  0, 0.5, 0, 0],
        "snare": [0, 0, 0, 0.15,  0.9, 0, 0.2, 0,  0, 0.15, 0, 0.25,  1, 0, 0.2, 0],
        "hat":   [0.65, 0, 0.3, 0.4,  0.65, 0.25, 0.4, 0.25,
                  0.7, 0, 0.35, 0.45,  0.65, 0.25, 0.4, 0.35],
    },
    "hip-hop": {
        "kick":  [1, 0, 0, 0,  0, 0, 0.35, 0,  0.8, 0, 0, 0.6,  0, 0, 0.25, 0],
        "snare": [0, 0, 0, 0,  0, 0, 0, 0,  1, 0, 0, 0,  0, 0, 0, 0],
        "hat":   [0.55, 0, 0.3, 0.2,  0.55, 0, 0.3, 0.2,
                  0.55, 0, 0.3, 0.2,  0.55, 0, 0.3, 0.2],
    },
    "electronic": {
        "kick":  [1, 0, 0, 0,  0.8, 0, 0, 0,  1, 0, 0, 0,  0.8, 0, 0, 0],
        "snare": [0, 0, 0, 0,  0.75, 0, 0, 0,  0, 0, 0, 0,  0.9, 0, 0, 0],
        "hat":   [0.45, 0.2, 0.35, 0.2,  0.45, 0.2, 0.35, 0.2,
                  0.45, 0.2, 0.35, 0.2,  0.45, 0.2, 0.35, 0.2],
    },
}

DRUM_GROOVES = {
    "straight_rock": {
        "kick":  [1, 0, 0, 0,  0, 0, 0, 0,  1, 0, 0.35, 0,  0, 0, 0, 0],
        "snare": [0, 0, 0, 0,  1, 0, 0, 0,  0, 0, 0, 0,  1, 0, 0.2, 0],
        "hat":   [0.65, 0, 0.4, 0,  0.65, 0, 0.4, 0,
                  0.65, 0, 0.4, 0,  0.65, 0, 0.4, 0],
    },
    "four_on_floor": {
        "kick":  [1, 0, 0, 0,  0.85, 0, 0, 0,  1, 0, 0, 0,  0.85, 0, 0, 0],
        "snare": [0, 0, 0, 0,  1, 0, 0, 0,  0, 0, 0, 0,  1, 0, 0, 0],
        "hat":   [0.6, 0, 0.4, 0,  0.6, 0, 0.4, 0,
                  0.6, 0, 0.4, 0,  0.6, 0, 0.4, 0],
    },
    "half_time": {
        "kick":  [1, 0, 0, 0,  0, 0, 0.25, 0,  0.8, 0, 0, 0,  0, 0, 0, 0],
        "snare": [0, 0, 0, 0,  0, 0, 0, 0,  1, 0, 0, 0,  0, 0, 0, 0],
        "hat":   [0.6, 0, 0, 0,  0.4, 0, 0, 0,
                  0.6, 0, 0, 0,  0.4, 0, 0, 0],
    },
    "breakbeat": {
        "kick":  [1, 0, 0, 0,  0, 0, 0.7, 0,  0.8, 0, 0, 0.45,  0, 0, 0, 0],
        "snare": [0, 0, 0, 0,  1, 0, 0, 0.25,  0, 0, 0.2, 0,  1, 0, 0, 0.4],
        "hat":   [0.45, 0.25, 0.35, 0.25,  0.5, 0.25, 0.35, 0.25,
                  0.45, 0.25, 0.35, 0.25,  0.5, 0.25, 0.35, 0.25],
    },
}

TRACKS = ("melody", "chords", "bass", "drums")
TRACK_GAINS = {"melody": 0.35, "chords": 0.20, "bass": 0.32, "drums": 0.50}
