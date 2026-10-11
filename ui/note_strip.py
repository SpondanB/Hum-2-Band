"""Custom canvas widget: simple piano roll with a moving playhead."""
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty
from kivy.uix.widget import Widget

ACCENT = (0.18, 0.85, 0.72)


class NoteStrip(Widget):
    notes = ListProperty([])            # [(midi, start_beat, duration_beats), ...]
    total_beats = NumericProperty(16)
    playhead = NumericProperty(-1)      # beats; < 0 hides the playhead

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.after:
            Color(1, 1, 1, 0.9)
            self._ph = Line(points=[-10, 0, -10, 0], width=dp(2))
        self.bind(pos=self._redraw, size=self._redraw, notes=self._redraw,
                  total_beats=self._redraw, playhead=self._move_playhead)

    def set_song(self, song):
        self.total_beats = song.bars * 4
        self.notes = [(n.midi, n.start, n.duration) for n in song.melody]

    def _redraw(self, *_):
        self.canvas.clear()
        w, h = self.width, self.height
        with self.canvas:
            Color(0.13, 0.15, 0.2, 1)
            Rectangle(pos=self.pos, size=self.size)
            tb = max(1, self.total_beats)
            for beat in range(int(tb) + 1):
                Color(1, 1, 1, 0.22 if beat % 4 == 0 else 0.07)
                x = self.x + beat / tb * w
                Line(points=[x, self.y, x, self.top], width=1)
            if self.notes:
                lo = min(n[0] for n in self.notes) - 2
                hi = max(n[0] for n in self.notes) + 2
                if hi - lo < 12:
                    hi = lo + 12
                row = h / (hi - lo + 1)
                Color(*ACCENT, 0.95)
                for midi, start, dur in self.notes:
                    Rectangle(pos=(self.x + start / tb * w + 1,
                                   self.y + (midi - lo) * row + 1),
                              size=(max(2, dur / tb * w - 2), max(2, row - 2)))
        self._move_playhead()

    def _move_playhead(self, *_):
        if self.playhead < 0:
            self._ph.points = [-10, 0, -10, 0]
        else:
            x = self.x + self.playhead / max(1, self.total_beats) * self.width
            self._ph.points = [x, self.y, x, self.top]
