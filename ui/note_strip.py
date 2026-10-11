"""Custom canvas widget: editable piano roll with a scale guide down the left side.

All editing rules live in core/editing.py (EditSession); this file only draws
the session and forwards mouse/touch events to it.
"""
from kivy.core.text import Label as CoreLabel
from kivy.core.window import Keyboard, Window
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty, ObjectProperty
from kivy.uix.widget import Widget

from core.editing import BLACK_PCS, EditSession, pitch_name, scale_degree, scale_pcs
from core.roll import RollGeometry

ACCENT = (0.94, 0.42, 0.19)
SELECTED = (1.0, 0.68, 0.32)
WARN = (0.86, 0.24, 0.20)
DARK = (0.08, 0.055, 0.055)

_KEYCODES = Keyboard.keycodes
# Kivy names its modifier keys inconsistently across versions, so accept all the spellings.
_MOD_KEYS = {
    "shift": {_KEYCODES[k] for k in ("shift", "lshift", "rshift") if k in _KEYCODES},
    "ctrl": {_KEYCODES[k] for k in ("ctrl", "lctrl", "rctrl") if k in _KEYCODES},
    "meta": {_KEYCODES[k] for k in ("super", "meta", "lmeta", "rmeta") if k in _KEYCODES},
}


class NoteStrip(Widget):
    total_beats = NumericProperty(16)
    playhead = NumericProperty(-1)            # beats; < 0 hides the playhead
    ui_scale = NumericProperty(1.0)           # follows the app-wide UI scale
    editable = BooleanProperty(False)
    edit_callback = ObjectProperty(None, allownone=True)      # f(list[Note]) after each edit
    preview_callback = ObjectProperty(None, allownone=True)   # f(midi) to audition a pitch

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session = EditSession(RollGeometry(gutter=dp(66), header=dp(18), edge_px=dp(8)))
        self.session.on_preview = self._preview
        self.has_song = False
        self._pan = None                      # (start_y, start_lo, row_h) while dragging the keys
        self._tex = {}
        self._mods = set()
        self._deferred = None
        self._reveal = False
        with self.canvas.after:
            Color(1, 1, 1, 0.9)
            self._ph = Line(points=[-10, 0, -10, 0], width=dp(2))
        self.bind(pos=self._redraw, size=self._on_resize, total_beats=self._redraw,
                  playhead=self._move_playhead, editable=self._redraw)
        Window.bind(on_key_down=self._key_down, on_key_up=self._key_up)
        self._apply_scale()

    def dispose(self):
        """Unhook the global keyboard handlers (call when the screen is torn down)."""
        Window.unbind(on_key_down=self._key_down, on_key_up=self._key_up)

    # ------------------------------------------------------------- scaling
    def on_ui_scale(self, *_):
        if hasattr(self, "session"):          # also fires while kv is still applying
            self._apply_scale()

    def _apply_scale(self):
        g, sc = self.session.geo, self.ui_scale
        g.gutter, g.header, g.edge_px = dp(66) * sc, dp(18) * sc, dp(8) * sc
        self._on_resize()

    def _on_resize(self, *_):
        """Keep every pitch row readable: budget rows by height, reach the rest by panning."""
        self._sync_geo()
        g, s = self.session.geo, self.session
        capacity = g.rows_for_height(g.plot_h, dp(13) * self.ui_scale)
        g.set_max_rows(capacity)
        if g.rows < capacity and s.notes:     # more room than before: show hidden notes again
            g.ensure_range(s.notes)
        self._redraw()

    # ------------------------------------------------------------ public API
    def set_song(self, song, fit=False):
        """Show the song's melody. fit=True re-centres the pitch range (new recording)."""
        s = self.session
        if s.dragging:                        # never swap notes under the user's mouse
            self._deferred = (song, fit)
            return
        s.set_scale(song.key_root, song.mode)
        total_beats = song.duration_beats if song.duration_beats is not None else song.bars * 4
        s.geo.total_beats = total_beats
        self.total_beats = total_beats
        s.load(song.melody, keep_selection=not fit)
        if fit:
            s.geo.fit(s.notes)
        elif self._reveal:                    # undo/redo: make sure restored notes are on screen
            s.geo.ensure_range(s.notes)
        self._reveal = False                  # otherwise keep the pitch range the user scrolled to
        self.has_song = True
        self._redraw()

    def reveal_all_on_next_update(self):
        self._reveal = True

    def set_grid(self, beats):
        self.session.grid = beats
        self._redraw()

    def set_scale_lock(self, enabled):
        self.session.scale_lock = bool(enabled)

    def select_all(self):
        self.session.select_all()
        self._redraw()

    def clear_selection(self):
        self.session.clear_selection()
        self._redraw()

    def delete_selected(self):
        self.session.delete_selected()
        self._after_edit()

    def transpose(self, steps=0, octaves=0):
        self.session.transpose(steps, octaves)
        self._after_edit()

    def nudge(self, beats):
        self.session.nudge(beats)
        self._after_edit()

    # ------------------------------------------------------------- plumbing
    def _preview(self, midi):
        if self.preview_callback:
            self.preview_callback(midi)

    def _sync_geo(self):
        self.session.geo.set_rect(self.x, self.y, self.width, self.height)

    def _after_edit(self):
        """Push committed edits to the controller, then redraw. Returns True if it committed."""
        s = self.session
        committed = s.take_dirty()
        if committed:
            s.geo.ensure_range(s.selected_notes())
            if self.edit_callback:
                self.edit_callback(s.result())
        self._redraw()
        return committed

    # -------------------------------------------------- keyboard modifiers
    def _key_down(self, window, key, scancode=None, codepoint=None, modifiers=None, *args):
        self._mods = set(modifiers or [])
        for name, codes in _MOD_KEYS.items():
            if key in codes:
                self._mods.add(name)
        return False

    def _key_up(self, window, key, *args):
        for name, codes in _MOD_KEYS.items():
            if key in codes:
                self._mods.discard(name)
        return False

    def _additive(self):
        mods = self._mods | set(getattr(Window, "modifiers", None) or [])
        return bool(mods & {"shift", "ctrl", "meta"})

    # ---------------------------------------------------------------- touch
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        self._sync_geo()
        if getattr(touch, "is_mouse_scrolling", False):         # wheel pans the pitch range
            if touch.button == "scrollup":
                self.session.geo.pan(-2)      # natural UI feel: wheel up moves pitch up
            elif touch.button == "scrolldown":
                self.session.geo.pan(2)
            self._redraw()
            return True
        g = self.session.geo
        if touch.x < g.plot_x and touch.y <= g.plot_top:         # piano keys: drag pans pitch
            touch.grab(self)
            self._pan = (touch.y, g.lo, g.row_h)
            if self.editable:
                self.session.press(touch.x, touch.y)             # click = audition the key
            return True
        if not self.editable:
            return True
        touch.grab(self)
        self.session.press(touch.x, touch.y, shift=self._additive(),
                           double=bool(getattr(touch, "is_double_tap", False)))
        self._after_edit()
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return False
        self._sync_geo()
        if self._pan is not None:
            y0, lo0, row_h = self._pan
            g = self.session.geo
            g.pan(lo0 - int(round((touch.y - y0) / row_h)) - g.lo)   # content follows the pointer
            self._redraw()
            return True
        self.session.drag(touch.x, touch.y)
        self._redraw()
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return False
        touch.ungrab(self)
        self._sync_geo()
        if self._pan is not None:
            self._pan = None
            return True
        self.session.release(touch.x, touch.y)
        committed = self._after_edit()
        deferred, self._deferred = self._deferred, None
        if deferred and not committed:        # after a commit the deferred song is already stale
            self.set_song(*deferred)
        return True

    # -------------------------------------------------------------- drawing
    def _label(self, text, size, color, bold=False):
        key = (text, size, color, bold)
        tex = self._tex.get(key)
        if tex is None:
            lab = CoreLabel(text=text, font_size=size, color=color, bold=bold)
            lab.refresh()
            tex = self._tex[key] = lab.texture
        return tex

    def _text(self, text, x, y, size, color, bold=False, align="left", w=0):
        """Draw text with its left edge at x (right edge when align='right'), centred on y."""
        tex = self._label(text, size, color, bold)
        if tex is None:
            return
        if align == "right":
            px = x - tex.width
        elif align == "center":
            px = x - tex.width / 2
        else:
            px = x
        Color(1, 1, 1, 1)
        Rectangle(texture=tex, pos=(px, y - tex.height / 2), size=tex.size)

    def _redraw(self, *_):
        self._sync_geo()
        s, g = self.session, self.session.geo
        pcs = scale_pcs(s.root, s.mode)
        rh = g.row_h
        sc = self.ui_scale
        font = max(8, int(dp(10) * sc))
        label_all = rh >= dp(11) * sc
        self.canvas.clear()
        with self.canvas:
            # ---- backgrounds
            Color(0.13, 0.15, 0.2, 1)
            Rectangle(pos=(g.plot_x, g.y), size=(g.plot_w, g.plot_h))
            Color(0.09, 0.10, 0.14, 1)
            Rectangle(pos=(g.x, g.plot_top), size=(g.w, g.header))

            # ---- pitch lanes + piano/scale gutter
            for p in range(g.lo, g.hi + 1):
                y0 = g.pitch_to_y(p)
                pc = p % 12
                in_scale, is_root, black = pc in pcs, pc == s.root, pc in BLACK_PCS
                if black:
                    Color(0, 0, 0, 0.20)
                    Rectangle(pos=(g.plot_x, y0), size=(g.plot_w, rh))
                if is_root:
                    Color(*ACCENT, 0.16)
                    Rectangle(pos=(g.plot_x, y0), size=(g.plot_w, rh))
                elif in_scale:
                    Color(*ACCENT, 0.05)
                    Rectangle(pos=(g.plot_x, y0), size=(g.plot_w, rh))
                Color(1, 1, 1, 0.13 if pc == 0 else 0.04)
                Line(points=[g.plot_x, y0, g.plot_right, y0], width=1)

                # key in the gutter: white/black like a piano, key root filled with the accent
                if is_root:
                    Color(*ACCENT, 1)
                elif black:
                    Color(0.16, 0.17, 0.21, 1)
                else:
                    Color(0.86, 0.88, 0.92, 1)
                Rectangle(pos=(g.x + 1, y0 + 0.5), size=(g.gutter - 2, max(1, rh - 1)))
                if in_scale and not is_root:
                    Color(*ACCENT, 1)
                    Rectangle(pos=(g.x + g.gutter - dp(5), y0 + 1),
                              size=(dp(4), max(1, rh - 2)))
                if label_all or is_root or pc == 0:
                    if is_root:
                        col = DARK + (1.0,)
                    elif black:
                        col = (0.85, 0.87, 0.9, 1.0 if in_scale else 0.5)
                    else:
                        col = (0.1, 0.11, 0.15, 1.0 if in_scale else 0.5)
                    cy = y0 + rh / 2
                    self._text(pitch_name(p, s.root, s.mode), g.x + dp(6), cy, font, col,
                               bold=in_scale)
                    deg = scale_degree(p, s.root, s.mode)
                    if deg and label_all:
                        self._text(str(deg), g.x + g.gutter - dp(9), cy, font,
                                   col[:3] + (0.75,), align="right")

            # ---- vertical grid (beats, bars, plus the snap grid when finer than a beat)
            tb = max(1, g.total_beats)
            if s.grid < 1.0 and g.plot_w / tb * s.grid >= 6:
                Color(1, 1, 1, 0.035)
                k = 0
                while k * s.grid <= tb:
                    if (k * s.grid) % 1 > 1e-9:
                        x = g.beat_to_x(k * s.grid)
                        Line(points=[x, g.y, x, g.plot_top], width=1)
                    k += 1
            for beat in range(int(tb) + 1):
                Color(1, 1, 1, 0.24 if beat % 4 == 0 else 0.08)
                x = g.beat_to_x(beat)
                Line(points=[x, g.y, x, g.plot_top + (g.header if beat % 4 == 0 else 0)], width=1)
                if beat % 4 == 0 and beat < tb:
                    self._text(str(beat // 4 + 1), x + dp(4), g.plot_top + g.header / 2, font,
                               (0.75, 0.78, 0.85, 1))

            # ---- notes
            for n in s.notes:
                if not s.in_view(n):          # scrolled out of range: drawing it would spill
                    continue                  # over the widgets above/below the chart
                x0, y0, x1, y1 = g.note_rect(n)
                sel = id(n) in s.selected
                w, h = max(2, x1 - x0 - 2), max(2, y1 - y0 - 2)
                Color(*(SELECTED if sel else ACCENT), 0.96)
                Rectangle(pos=(x0 + 1, y0 + 1), size=(w, h))
                if w > dp(14):                                    # resize handle
                    Color(0, 0, 0, 0.22)
                    Rectangle(pos=(x1 - dp(5), y0 + 1), size=(dp(4), h))
                if sel:
                    Color(1, 1, 1, 0.95)
                    Line(rectangle=(x0 + 1, y0 + 1, w, h), width=1.2)
                if n.midi % 12 not in pcs:                        # out of key (snap to key off)
                    Color(*WARN, 1)
                    Rectangle(pos=(x0 + 1, y0 + 1), size=(w, max(2, dp(2))))

            # ---- box selection
            if s.marquee:
                mx0, my0, mx1, my1 = s.marquee
                lx, rx = max(g.plot_x, min(mx0, mx1)), min(g.plot_right, max(mx0, mx1))
                by, ty = max(g.y, min(my0, my1)), min(g.plot_top, max(my0, my1))
                bx, bw, bh = lx, max(0, rx - lx), max(0, ty - by)
                Color(1, 1, 1, 0.10)
                Rectangle(pos=(bx, by), size=(bw, bh))
                Color(1, 1, 1, 0.65)
                Line(rectangle=(bx, by, bw, bh), width=1)

            # ---- empty-state hint
            if not s.notes:
                msg = ("Double-click to add a note" if self.has_song else
                       "Record a hum or load the demo melody - then edit it here")
                self._text(msg, g.plot_x + g.plot_w / 2, g.y + g.plot_h / 2, int(dp(15) * sc),
                           (0.7, 0.73, 0.8, 0.7), align="center")
        self._move_playhead()

    def _move_playhead(self, *_):
        g = self.session.geo
        if self.playhead < 0:
            self._ph.points = [-10, 0, -10, 0]
        else:
            x = g.beat_to_x(self.playhead)
            self._ph.points = [x, g.y, x, self.top]
