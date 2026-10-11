"""Main screen logic. The ONLY layer (besides note_strip/main) that imports Kivy."""
import os
import time

from kivy.clock import Clock
from kivy.properties import (BooleanProperty, ListProperty, NumericProperty,
                             StringProperty)
from kivy.uix.floatlayout import FloatLayout

from core.controller import Controller
from core.patterns import GENRE_LABELS, NOTE_NAMES
from ui.note_strip import NoteStrip  # noqa: F401  (needed by hum.kv)

KEY_CHOICES = ["Key: Auto"] + [f"{n} {m}" for m in ("major", "minor") for n in NOTE_NAMES]


def _ui(fn):
    """Wrap a callback so it always runs on the Kivy thread."""
    def wrapper(*args, **kwargs):
        Clock.schedule_once(lambda dt: fn(*args, **kwargs), 0)
    return wrapper


class MainScreen(FloatLayout):
    controller = None  # class-level so kv-triggered handlers can run safely at init

    state = StringProperty("idle")
    status_text = StringProperty("Tap Record, then hum 4 bars")
    key_text = StringProperty("Key: --")
    chords_text = StringProperty("")
    live_note = StringProperty("--")
    level = NumericProperty(0)
    progress = NumericProperty(0)
    big_text = StringProperty("")
    record_text = StringProperty("Record")
    play_text = StringProperty("Play")
    can_record = BooleanProperty(True)
    can_play = BooleanProperty(False)
    is_recording = BooleanProperty(False)
    key_choices = ListProperty(KEY_CHOICES)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ev_count = self._ev_prog = self._ev_tempo = None
        self.controller = Controller(on_state=_ui(self._on_state),
                                     on_live=_ui(self._on_live),
                                     on_result=_ui(self._on_result))
        Clock.schedule_once(lambda dt: self.controller.start(), 0.3)
        Clock.schedule_interval(self._tick_playhead, 1 / 60.0)

    # ----------------------------------------------------- controller events
    def _on_live(self, note, level):
        self.live_note = note
        self.level = level

    def _on_result(self, song):
        self.ids.note_strip.set_song(song)
        self.key_text = self.controller.key_text()
        self.chords_text = self.controller.chords_text()
        self.can_play = True

    def _on_state(self, state, info):
        self.state = state
        self._cancel(("_ev_count", "_ev_prog"))
        self.big_text = ""
        self.is_recording = False
        busy = state in ("counting", "recording", "processing")
        self.can_record = not busy
        self.can_play = (not busy) and self.controller.song is not None
        self.record_text = "Retry" if state == "error" else (
            "Re-record" if self.controller.song else "Record")
        self.play_text = "Stop" if state == "playing" else "Play"
        if state != "recording":
            self.progress = 0

        if state == "idle":
            self.status_text = "Tap Record, then hum 4 bars"
        elif state == "counting":
            self.status_text = "Get ready..."
            self._beat = 1
            self.big_text = "1"
            self._ev_count = Clock.schedule_interval(self._count_tick, 60.0 / info["bpm"])
        elif state == "recording":
            self.status_text = "Recording - hum your tune!"
            self.is_recording = True
            self._rec_start, self._rec_dur = time.monotonic(), info["duration"]
            self._ev_prog = Clock.schedule_interval(self._prog_tick, 1 / 30.0)
        elif state == "processing":
            self.status_text = "Building your band..."
        elif state in ("ready", "playing"):
            self.status_text = "Playing" if state == "playing" else "Ready"
        elif state == "error":
            self.status_text = info.get("message", "Something went wrong")

    # ------------------------------------------------------------- timers
    def _cancel(self, names):
        for n in names:
            ev = getattr(self, n)
            if ev:
                ev.cancel()
            setattr(self, n, None)

    def _count_tick(self, dt):
        self._beat += 1
        if self._beat > 4:
            return False
        self.big_text = str(self._beat)

    def _prog_tick(self, dt):
        self.progress = min(1.0, (time.monotonic() - self._rec_start) / self._rec_dur)

    def _tick_playhead(self, dt):
        beats = self.controller.playhead_beats() if self.controller else None
        self.ids.note_strip.playhead = -1 if beats is None else beats

    # ------------------------------------------------------- user actions
    def on_record(self):
        self.controller.record()

    def on_demo(self):
        self.controller.load_demo()

    def on_play_stop(self):
        if self.state == "playing":
            self.controller.stop()
        else:
            self.controller.play()

    def on_genre(self, text):
        if self.controller:
            self.controller.set_genre(GENRE_LABELS.get(text, "pop"))

    def on_tempo(self, value):
        if not self.controller:
            return
        if self._ev_tempo:
            self._ev_tempo.cancel()           # debounce slider drags
        self._ev_tempo = Clock.schedule_once(
            lambda dt: self.controller.set_tempo(value), 0.3)

    def on_key_override(self, text):
        if not self.controller:
            return
        if text == "Key: Auto":
            self.controller.set_key_override(None)
        else:
            name, mode = text.split()
            self.controller.set_key_override((NOTE_NAMES.index(name), mode))

    def on_track(self, name, enabled):
        if self.controller:
            self.controller.set_track_enabled(name, enabled)

    def on_save(self):
        path = os.path.join(os.path.expanduser("~"), "hum_to_band.wav")
        if self.controller.save_wav(path):
            self.status_text = f"Saved {path}"
