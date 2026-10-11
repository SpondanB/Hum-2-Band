"""Shared data formats (no Kivy imports)."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Note:
    midi: int        # e.g. 60 = C4
    start: float     # in beats from start of loop
    duration: float  # in beats

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass
class Song:
    key_root: int       # 0 to 11 (C = 0)
    mode: str           # "major" or "minor"
    bpm: int
    bars: int           # 4 for MVP
    melody: list
    chords: list        # one chord per bar, stored as stacked notes
    bass: list
    genre: str          # "pop" or "lo-fi"


@dataclass
class PitchFrame:
    t: float                  # seconds (relative to capture start when recording)
    midi: Optional[float]     # None = unvoiced / gated
    rms: float = 0.0
    conf: float = 0.0
