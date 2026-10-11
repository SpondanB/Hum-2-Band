"""Melody editing for the piano roll. No Kivy imports (NFR-8).

`EditSession` is the whole editor minus drawing: the Kivy widget only forwards
press / drag / release events (in pixels) and reads back `notes`, `selected`
and `marquee` to draw them. That keeps every editing rule unit-testable.

Editing model (DAW / MIDI-editor style):
* click a note = select it; Shift/Ctrl-click = add to / remove from the selection
* drag on empty space = box-select
* drag any selected note = move the WHOLE selection (time snapped to the grid,
  pitch by scale steps when "snap to key" is on, otherwise by semitones)
* drag a note's right edge = resize the whole selection
* double-click empty space = add a note, double-click a note = delete it
* commands: delete, transpose, nudge, select all
Changes are reported once per gesture through `take_dirty()`.
"""
import math
from bisect import bisect_left

from .analysis import quantize_pitch
from .models import Note
from .patterns import SCALES
from .roll import PITCH_MAX, PITCH_MIN, RollGeometry

SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
BLACK_PCS = frozenset({1, 3, 6, 8, 10})
FLAT_MAJOR_ROOTS = frozenset({5, 10, 3, 8, 1})     # F, Bb, Eb, Ab, Db


# --------------------------------------------------------------- scale helpers
def scale_pcs(root, mode):
    return {(root + i) % 12 for i in SCALES[mode]}


def scale_pitches(root, mode, lo=PITCH_MIN, hi=PITCH_MAX):
    pcs = scale_pcs(root, mode)
    return [p for p in range(lo, hi + 1) if p % 12 in pcs]


def scale_degree(midi, root, mode):
    """1..7 for in-scale pitches, None otherwise."""
    rel = (midi - root) % 12
    return SCALES[mode].index(rel) + 1 if rel in SCALES[mode] else None


def uses_flats(root, mode):
    major_root = root if mode == "major" else (root + 3) % 12
    return major_root in FLAT_MAJOR_ROOTS


def pitch_name(midi, root=0, mode="major"):
    """Note name with octave, spelled with flats in flat keys (e.g. 'Bb3')."""
    names = FLAT_NAMES if uses_flats(root, mode) else SHARP_NAMES
    return f"{names[midi % 12]}{midi // 12 - 1}"


def _nearest_index(pitches, midi):
    i = bisect_left(pitches, midi)
    if i == 0:
        return 0
    if i == len(pitches):
        return len(pitches) - 1
    return i if pitches[i] - midi < midi - pitches[i - 1] else i - 1


def scale_index(midi, root, mode):
    """Position of the in-scale pitch nearest `midi` in the full scale ladder."""
    pitches = scale_pitches(root, mode)
    return _nearest_index(pitches, quantize_pitch(midi, root, mode))


def shift_diatonic(midi, steps, root, mode):
    """Move `midi` by `steps` notes up/down the scale (out-of-scale input is snapped first)."""
    pitches = scale_pitches(root, mode)
    i = _nearest_index(pitches, quantize_pitch(midi, root, mode)) + steps
    return pitches[max(0, min(len(pitches) - 1, i))]


def _snap(x, grid):
    return math.floor(x / grid + 0.5) * grid


# ------------------------------------------------------------------- the editor
class EditSession:
    MIN_DRAG_PX = 3

    def __init__(self, geometry=None, root=0, mode="major", grid=0.5, scale_lock=True):
        self.geo = geometry or RollGeometry()
        self.root, self.mode = root, mode
        self.grid = grid                  # beats; 1.0 = quarter, 0.5 = 8th, 0.25 = 16th
        self.scale_lock = scale_lock      # "snap to key"
        self.default_len = 1.0            # length of newly added notes (follows last resize)
        self.notes = []                   # list[Note], edited in place
        self.selected = set()             # id(note) of selected notes
        self.marquee = None               # (x0, y0, x1, y1) while box-selecting
        self.on_preview = None            # callable(midi): audition a pitch
        self._dirty = False
        self._reset_drag()

    # ------------------------------------------------------------------ state
    def _reset_drag(self):
        self._mode = None                 # None | "move" | "resize" | "marquee"
        self._orig = {}
        self._moved = False
        self._narrow = None
        self._grab_note = None
        self._last_preview = None

    @property
    def dragging(self):
        return self._mode is not None

    def take_dirty(self):
        """True once after any committed change (the caller then pushes `result()`)."""
        d, self._dirty = self._dirty, False
        return d

    def set_scale(self, root, mode):
        self.root, self.mode = root, mode

    def load(self, notes, keep_selection=False):
        """Replace the notes (copies). Selection survives by position if asked and possible."""
        keep = ({i for i, n in enumerate(self.notes) if id(n) in self.selected}
                if keep_selection and len(notes) == len(self.notes) else set())
        self.notes = [Note(n.midi, n.start, n.duration) for n in notes]
        self.selected = {id(self.notes[i]) for i in keep}
        self.marquee = None
        self._reset_drag()

    def result(self):
        return [Note(n.midi, n.start, n.duration) for n in self.notes]

    def selected_notes(self):
        return [n for n in self.notes if id(n) in self.selected]

    # -------------------------------------------------------------- selection
    def select_all(self):
        self.selected = {id(n) for n in self.notes}

    def clear_selection(self):
        self.selected = set()

    def in_view(self, note):
        """False for notes scrolled out of the visible pitch range (not drawn, not clickable)."""
        return self.geo.lo <= note.midi <= self.geo.hi

    def hit_test(self, x, y):
        """(note, 'body'|'edge') under the point, topmost first; (None, None) if empty."""
        g = self.geo
        for n in reversed(self.notes):
            if not self.in_view(n):
                continue
            x0, y0, x1, y1 = g.note_rect(n)
            if x0 - 1 <= x <= x1 + 1 and y0 <= y <= y1:
                edge = min(g.edge_px, max(2.0, (x1 - x0) * 0.4))
                return n, ("edge" if x >= x1 - edge else "body")
        return None, None

    # ---------------------------------------------------------------- gestures
    def press(self, x, y, shift=False, double=False):
        g = self.geo
        self._reset_drag()
        if y > g.plot_top:
            return
        if x < g.plot_x:                               # piano gutter: audition that key
            self._preview(g.y_to_pitch(y))
            return
        note, zone = self.hit_test(x, y)
        if note is not None:
            if double:
                self._remove([note])
                self._dirty = True
                return
            nid = id(note)
            if shift:
                if nid in self.selected:
                    self.selected.discard(nid)
                    return
                self.selected.add(nid)
            elif nid not in self.selected:
                self.selected = {nid}
            else:
                self._narrow = note        # plain click inside a group narrows it on release
            self._begin_drag("resize" if zone == "edge" else "move", x, y, note)
            if zone == "body":
                self._preview(note.midi)
            return
        if double:
            self._add_at(x, y)
            return
        self._mode = "marquee"
        self._grab = (x, y)
        self._base = set(self.selected) if shift else set()
        self.selected = set(self._base)
        self.marquee = (x, y, x, y)

    def _begin_drag(self, kind, x, y, note):
        g = self.geo
        self._mode = kind
        self._grab = (x, y)
        self._grab_beat = g.x_to_beat(x)
        self._grab_row = g.y_to_pitch(y)
        self._grab_note = note
        self._orig = {id(n): (n.midi, n.start, n.duration) for n in self.selected_notes()}
        self._moved = False

    def drag(self, x, y):
        if self._mode is None:
            return
        if self._mode == "marquee":
            x0, y0 = self._grab
            self.marquee = (x0, y0, x, y)
            rx0, rx1 = sorted((x0, x))
            ry0, ry1 = sorted((y0, y))
            hits = set()
            for n in self.notes:
                if not self.in_view(n):
                    continue
                nx0, ny0, nx1, ny1 = self.geo.note_rect(n)
                if nx0 <= rx1 and nx1 >= rx0 and ny0 <= ry1 and ny1 >= ry0:
                    hits.add(id(n))
            self.selected = self._base | hits
            return
        if not self._moved:
            gx, gy = self._grab
            if abs(x - gx) < self.MIN_DRAG_PX and abs(y - gy) < self.MIN_DRAG_PX:
                return
            self._moved = True
        if self._mode == "resize":
            self._apply_resize(x)
        else:
            self._apply_move(x, y)

    def release(self, x=None, y=None):
        mode = self._mode
        if mode in ("move", "resize"):
            if self._moved:
                changed = any((n.midi, n.start, n.duration) != self._orig[id(n)]
                              for n in self.selected_notes() if id(n) in self._orig)
                if mode == "resize" and self._grab_note is not None:
                    self.default_len = self._grab_note.duration
                if changed:
                    self._tidy()
                    self._dirty = True
            elif self._narrow is not None:
                self.selected = {id(self._narrow)}
        elif mode == "marquee":
            self.marquee = None
        self._reset_drag()

    # ----------------------------------------------------------- drag helpers
    def _apply_move(self, x, y):
        g = self.geo
        orig = self._orig
        d = _snap(g.x_to_beat(x) - self._grab_beat, self.grid)
        d = max(d, -min(o[1] for o in orig.values()))
        d = min(d, g.total_beats - max(o[1] + o[2] for o in orig.values()))

        rows = g.y_to_pitch(y) - self._grab_row
        grabbed = orig[id(self._grab_note)][0]
        if self.scale_lock:                                  # move by scale steps
            steps = (scale_index(quantize_pitch(grabbed + rows, self.root, self.mode),
                                 self.root, self.mode)
                     - scale_index(grabbed, self.root, self.mode))
            move = lambda m, s: shift_diatonic(m, s, self.root, self.mode)
        else:                                                # move by semitones
            steps = rows
            move = lambda m, s: m + s
        while steps and any(not (g.lo <= move(o[0], steps) <= g.hi) for o in orig.values()):
            steps -= 1 if steps > 0 else -1                  # keep the group on screen

        for n in self.selected_notes():
            o = orig.get(id(n))
            if o is None:
                continue
            n.start = o[1] + d
            n.midi = move(o[0], steps) if steps else o[0]
        if self._grab_note.midi != self._last_preview:
            self._last_preview = self._grab_note.midi
            if steps:
                self._preview(self._grab_note.midi)

    def _apply_resize(self, x):
        g = self.geo
        d = _snap(g.x_to_beat(x) - self._grab_beat, self.grid)
        for n in self.selected_notes():
            o = self._orig.get(id(n))
            if o is None:
                continue
            n.duration = max(0.05, min(max(o[2] + d, self.grid), g.total_beats - o[1]))

    # --------------------------------------------------------------- add/remove
    def _add_at(self, x, y):
        g = self.geo
        start = math.floor(g.x_to_beat(x) / self.grid) * self.grid
        start = max(0.0, min(start, g.total_beats - self.grid))
        midi = g.y_to_pitch(y)
        if self.scale_lock:
            midi = quantize_pitch(midi, self.root, self.mode)
        self.add_note(midi, start)

    def add_note(self, midi, start, duration=None):
        total = self.geo.total_beats
        start = max(0.0, min(start, total - self.grid))
        dur = min(duration or self.default_len, total - start)
        for n in self.notes:                     # same pitch + start already there: just select it
            if n.midi == midi and abs(n.start - start) < 1e-9:
                self.selected = {id(n)}
                return n
        note = Note(int(midi), start, dur)
        self.notes.append(note)
        self.selected = {id(note)}
        self._tidy()
        self._dirty = True
        self._preview(note.midi)
        return note

    def _remove(self, victims):
        ids = {id(n) for n in victims}
        self.notes = [n for n in self.notes if id(n) not in ids]
        self.selected -= ids

    def delete_selected(self):
        victims = self.selected_notes()
        if not victims:
            return False
        self._remove(victims)
        self._dirty = True
        return True

    def _tidy(self):
        """Merge exact duplicates (same pitch + start, keep the longest) and sort by time."""
        best = {}
        for n in self.notes:
            k = (n.midi, round(n.start, 6))
            if k not in best or n.duration > best[k].duration:
                best[k] = n
        kept = {id(n) for n in best.values()}
        if len(kept) != len(self.notes):
            gone = [n for n in self.notes if id(n) not in kept]
            for n in gone:                       # a selected duplicate passes selection on
                if id(n) in self.selected:
                    self.selected.discard(id(n))
                    self.selected.add(id(best[(n.midi, round(n.start, 6))]))
            self.notes = [n for n in self.notes if id(n) in kept]
        self.notes.sort(key=lambda n: (n.start, n.midi))

    # ------------------------------------------------------------- commands
    def transpose(self, steps=0, octaves=0):
        """Move the selection up/down: scale steps if snap-to-key is on, else semitones."""
        sel = self.selected_notes()
        if not sel:
            return False
        if self.scale_lock:
            new = [shift_diatonic(n.midi, steps + 7 * octaves, self.root, self.mode) for n in sel]
        else:
            new = [n.midi + steps + 12 * octaves for n in sel]
        if all(m == n.midi for m, n in zip(new, sel)) or \
                any(not (PITCH_MIN <= m <= PITCH_MAX) for m in new):
            return False
        for n, m in zip(sel, new):
            n.midi = m
        self._tidy()
        self.geo.ensure_range(sel)
        self._dirty = True
        self._preview(new[0])
        return True

    def nudge(self, beats):
        sel = self.selected_notes()
        if not sel:
            return False
        d = max(beats, -min(n.start for n in sel))
        d = min(d, self.geo.total_beats - max(n.end for n in sel))
        if abs(d) < 1e-9:
            return False
        for n in sel:
            n.start += d
        self._tidy()
        self._dirty = True
        return True

    def _preview(self, midi):
        if self.on_preview:
            try:
                self.on_preview(int(midi))
            except Exception:
                pass
