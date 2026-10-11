"""Piano-roll geometry: beats/pitches <-> pixels. No Kivy imports.

Layout of the widget rectangle (Kivy coordinates, y grows upward):

    +--------+---------------------------------------+  <- top
    | gutter |  header (bar numbers)                 |
    | (keys) +---------------------------------------+  <- plot_top
    |        |                                       |
    |        |  plot: one row per semitone           |
    +--------+---------------------------------------+  <- y
"""
import math

PITCH_MIN, PITCH_MAX = 21, 108      # A0 .. C8, plenty for a hummed tune
DEFAULT_LO, DEFAULT_HI = 48, 72     # C3 .. C5 shown on an empty chart


class RollGeometry:
    def __init__(self, x=0.0, y=0.0, w=1000.0, h=400.0, gutter=64.0, header=18.0,
                 total_beats=16, lo=DEFAULT_LO, hi=DEFAULT_HI, edge_px=8.0):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.gutter, self.header = gutter, header
        self.total_beats = total_beats
        self.lo, self.hi = lo, hi          # visible pitch range, inclusive
        self.edge_px = edge_px             # grab zone for resizing a note

    # ------------------------------------------------------------ rectangle
    def set_rect(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, max(1.0, w), max(1.0, h)

    @property
    def plot_x(self):
        return self.x + self.gutter

    @property
    def plot_w(self):
        return max(1.0, self.w - self.gutter)

    @property
    def plot_right(self):
        return self.plot_x + self.plot_w

    @property
    def plot_top(self):
        return self.y + self.h - self.header

    @property
    def plot_h(self):
        return max(1.0, self.h - self.header)

    @property
    def rows(self):
        return self.hi - self.lo + 1

    @property
    def row_h(self):
        return self.plot_h / self.rows

    # -------------------------------------------------------------- mapping
    def beat_to_x(self, beat):
        return self.plot_x + beat / max(1, self.total_beats) * self.plot_w

    def x_to_beat(self, x):
        return (x - self.plot_x) / self.plot_w * max(1, self.total_beats)

    def pitch_to_y(self, pitch):
        """Bottom edge of the row for `pitch`."""
        return self.y + (pitch - self.lo) * self.row_h

    def y_to_pitch(self, y):
        """Pitch of the row under `y`, clamped to the visible range."""
        p = self.lo + int(math.floor((y - self.y) / self.row_h))
        return max(self.lo, min(self.hi, p))

    def note_rect(self, note):
        """(x0, y0, x1, y1) of a note, at least 3 px wide so it can always be grabbed."""
        x0 = self.beat_to_x(note.start)
        x1 = max(x0 + 3.0, self.beat_to_x(note.start + note.duration))
        y0 = self.pitch_to_y(note.midi)
        return x0, y0, x1, y0 + self.row_h

    # ----------------------------------------------------------- view range
    def _clamp_span(self, lo, hi):
        span = hi - lo
        lo = max(PITCH_MIN, min(lo, PITCH_MAX - span))
        return lo, lo + span

    def fit(self, notes, min_span=16, margin=3):
        """Choose a visible range around the notes (used for a fresh melody)."""
        if not notes:
            self.lo, self.hi = DEFAULT_LO, DEFAULT_HI
            return
        lo = min(n.midi for n in notes) - margin
        hi = max(n.midi for n in notes) + margin
        if hi - lo + 1 < min_span:
            extra = min_span - (hi - lo + 1)
            lo -= extra // 2
            hi += extra - extra // 2
        self.lo, self.hi = self._clamp_span(max(PITCH_MIN, lo), min(PITCH_MAX, hi))

    def ensure_range(self, notes, margin=1):
        """Grow (never shrink) the visible range so every note stays on screen."""
        if not notes:
            return
        lo = min(self.lo, max(PITCH_MIN, min(n.midi for n in notes) - margin))
        hi = max(self.hi, min(PITCH_MAX, max(n.midi for n in notes) + margin))
        self.lo, self.hi = lo, hi

    def pan(self, semitones):
        self.lo, self.hi = self._clamp_span(self.lo + semitones, self.hi + semitones)
