"""Main screen logic. The ONLY layer (besides note_strip/main) that imports Kivy."""
import os
import threading
import time

from kivy.clock import Clock
from kivy.core.window import Keyboard, Window
from kivy.properties import (BooleanProperty, ListProperty, NumericProperty,
                             StringProperty)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput

from core.controller import Controller
from core.patterns import (BASS_STYLE_OPTIONS, DRUM_STYLE_OPTIONS, GENRE_LABELS,
                           NOTE_NAMES)
from ui.note_strip import NoteStrip  # noqa: F401  (needed by hum.kv)

GRID_CHOICES = {"Grid: 1/4": 1.0, "Grid: 1/8": 0.5, "Grid: 1/16": 0.25}
EDIT_HINT = ("Drag: move | right edge: resize | Shift-click or box: multi-select | "
             "Double-click: add/delete | Del, arrows, Ctrl+Z")
_KEY_NAMES = {code: name for name, code in Keyboard.keycodes.items()}

KEY_CHOICES = ["Key: Auto"] + [f"{n} {m}" for m in ("major", "minor") for n in NOTE_NAMES]


def _ui(fn):
    """Wrap a callback so it always runs on the Kivy thread."""
    def wrapper(*args, **kwargs):
        Clock.schedule_once(lambda dt: fn(*args, **kwargs), 0)
    return wrapper


class MainScreen(FloatLayout):
    controller = None  # class-level so kv-triggered handlers can run safely at init

    state = StringProperty("idle")
    status_text = StringProperty("Ready to hum. Press Record when you're set.")
    key_text = StringProperty("Key: --")
    chords_text = StringProperty("")
    live_note = StringProperty("--")
    level = NumericProperty(0)
    progress = NumericProperty(0)
    record_limit = NumericProperty(45.0)
    record_limit_text = StringProperty("45s")
    bass_style_choices = ListProperty(list(BASS_STYLE_OPTIONS))
    drum_style_choices = ListProperty(list(DRUM_STYLE_OPTIONS))
    bass_style_text = StringProperty("Bass: Auto")
    drum_style_text = StringProperty("Drums: Auto")
    big_text = StringProperty("")
    record_text = StringProperty("Record")
    play_text = StringProperty("Play")
    can_record = BooleanProperty(True)
    can_play = BooleanProperty(False)
    can_reference = BooleanProperty(False)
    reference_with_band = BooleanProperty(False)
    is_recording = BooleanProperty(False)
    key_choices = ListProperty(KEY_CHOICES)
    default_in = StringProperty("Mic: system default")
    default_out = StringProperty("Output: system default")
    input_names = ListProperty(["Mic: system default"])
    output_names = ListProperty(["Output: system default"])
    # --- melody editing
    can_edit = BooleanProperty(False)
    can_undo = BooleanProperty(False)
    can_redo = BooleanProperty(False)
    scale_lock = BooleanProperty(True)
    grid_choices = ListProperty(list(GRID_CHOICES))
    edit_hint = StringProperty(EDIT_HINT)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ev_count = self._ev_prog = self._ev_tempo = None
        self.controller = Controller(on_state=_ui(self._on_state),
                                     on_live=_ui(self._on_live),
                                     on_result=_ui(self._on_result))
        self.controller.set_max_record_seconds(self.record_limit)
        self._in_map, self._out_map = {}, {}
        self._saving = False
        self._local_rev = 0          # newest melody revision the user created on screen
        self._seen_gen = 0           # last recognised/loaded melody shown (to re-centre the roll)
        Window.bind(on_key_down=self._on_key_down)
        Clock.schedule_once(self._startup, 0.3)
        Clock.schedule_interval(self._tick_playhead, 1 / 60.0)

    # --------------------------------------------------------------- audio devices
    def _startup(self, dt):
        self._populate_devices()
        threading.Thread(target=self.controller.start, daemon=True).start()

    def _populate_devices(self):
        ins, outs = self.controller.list_devices()
        self._in_map = {label: idx for idx, label, _ in ins}
        self._out_map = {label: idx for idx, label, _ in outs}
        self.input_names = [self.default_in] + list(self._in_map)
        self.output_names = [self.default_out] + list(self._out_map)

    def _reset_spinners(self):
        c = self.controller
        self.ids.in_dev.text = next((k for k, v in self._in_map.items()
                                     if v == c.input_device), self.default_in)
        self.ids.out_dev.text = next((k for k, v in self._out_map.items()
                                      if v == c.output_device), self.default_out)

    def on_refresh(self):
        """Re-read OS devices + default mic/speakers (after changing sound settings)."""
        if self.state in ("counting", "recording", "processing"):
            return
        self.status_text = "Refreshing audio devices..."
        def work():
            self.controller.restart_audio()
            Clock.schedule_once(lambda dt: (self._populate_devices(), self._reset_spinners()), 0)
        threading.Thread(target=work, daemon=True).start()

    def on_input_device(self, text):
        if not self.controller:
            return
        idx = self._in_map.get(text)          # "system default" -> None
        if idx != self.controller.input_device:
            threading.Thread(target=self.controller.set_input_device,
                             args=(idx,), daemon=True).start()

    def on_output_device(self, text):
        if not self.controller:
            return
        idx = self._out_map.get(text)
        if idx != self.controller.output_device:
            threading.Thread(target=self.controller.set_output_device,
                             args=(idx,), daemon=True).start()

    def on_gain(self, value):
        if self.controller:
            self.controller.set_input_gain(value)

    def set_record_limit(self, value):
        self.record_limit = float(value)

    def on_record_limit(self, instance, value):
        self.record_limit_text = f"{int(round(value))}s"
        if self.controller:
            self.controller.set_max_record_seconds(value)

    # ----------------------------------------------------- controller events
    def _on_live(self, note, level):
        self.live_note = note
        self.level = level

    def _on_result(self, song):
        c = self.controller
        # A result built from an older melody than the user's latest on-screen edit is stale:
        # skip it (a newer one is on its way) so the roll never jumps back.
        if c.built_rev >= self._local_rev:
            fit = c.melody_gen != self._seen_gen
            self._seen_gen = c.melody_gen
            self.ids.note_strip.set_song(c.song or song, fit=fit)
        self.scale_lock = c.snap_to_scale
        self.ids.note_strip.set_scale_lock(c.snap_to_scale)
        self.key_text = c.key_text()
        self.chords_text = c.chords_text()
        self.can_play = True
        self._sync_edit_state()

    def _on_state(self, state, info):
        self.state = state
        self._cancel(("_ev_count", "_ev_prog"))
        self.big_text = ""
        self.is_recording = False
        busy = state in ("counting", "recording", "processing")
        self.can_record = not busy or state == "recording"
        self.can_play = (not busy) and self.controller.song is not None
        self.can_reference = bool(not busy and self.controller.reference_audio is not None
                      and len(self.controller.reference_audio))
        self._sync_edit_state()
        self.record_text = ("Stop" if state == "recording" else
                            "Retry" if state == "error" else
                            "Re-record" if self.controller.song else "Record")
        self.play_text = "Stop" if state == "playing" else "Play"
        if state != "recording":
            self.progress = 0

        if state == "idle":
            self.status_text = "Ready to hum. Press Record when you're set."
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
        elif state == "reference":
            self.status_text = "Playing hummed reference"
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
        if self._beat > 3:
            return False
        self.big_text = str(self._beat)

    def _prog_tick(self, dt):
        self.progress = min(1.0, (time.monotonic() - self._rec_start) / self._rec_dur)

    def _tick_playhead(self, dt):
        beats = self.controller.playhead_beats() if self.controller else None
        self.ids.note_strip.playhead = -1 if beats is None else beats

    # ------------------------------------------------------ melody editing
    def _sync_edit_state(self):
        c = self.controller
        busy = self.state in ("counting", "recording", "processing")
        self.can_edit = bool(c and c.song is not None and not busy)
        self.can_undo = bool(c and c.can_undo and not busy)
        self.can_redo = bool(c and c.can_redo and not busy)

    def on_edit_commit(self, notes):
        """The user finished an edit gesture on the piano roll."""
        if not self.controller:
            return
        rev = self.controller.set_melody(notes)
        if rev is not None:
            self._local_rev = rev
            self.status_text = "Melody edited - the band follows on the next loop"
        self._sync_edit_state()

    def on_preview_note(self, midi):
        if self.controller:
            self.controller.preview_note(midi)

    def _history(self, step):
        rev = step()
        if rev is not None:
            self._local_rev = rev
            self.ids.note_strip.clear_selection()
            self.ids.note_strip.reveal_all_on_next_update()
        self._sync_edit_state()

    def on_undo(self):
        if self.controller:
            self._history(self.controller.undo)

    def on_redo(self):
        if self.controller:
            self._history(self.controller.redo)

    def on_select_all(self):
        self.ids.note_strip.select_all()

    def on_delete_notes(self):
        self.ids.note_strip.delete_selected()

    def on_grid(self, text):
        strip = self.ids.get("note_strip")       # also fires while the kv is still loading
        if strip is not None:
            strip.set_grid(GRID_CHOICES.get(text, 0.5))

    def on_scale_lock(self, enabled):
        strip = self.ids.get("note_strip")
        if strip is not None:
            strip.set_scale_lock(enabled)
        if self.controller and enabled != self.controller.snap_to_scale:
            self.controller.set_scale_lock(enabled)

    def _on_key_down(self, window, key, scancode=None, codepoint=None, modifiers=None, *args):
        strip = self.ids.get("note_strip")
        if strip is None or not self.can_edit:
            return False
        mods = set(modifiers or [])
        ctrl, shift = bool(mods & {"ctrl", "meta"}), "shift" in mods
        name = _KEY_NAMES.get(key)
        grid = strip.session.grid
        if ctrl and name == "a":
            strip.select_all()
        elif ctrl and name == "z" and not shift:
            self.on_undo()
        elif ctrl and (name == "y" or (name == "z" and shift)):
            self.on_redo()
        elif name in ("delete", "backspace"):
            strip.delete_selected()
        elif name in ("up", "down"):
            sign = 1 if name == "up" else -1
            strip.transpose(steps=0 if shift else sign, octaves=sign if shift else 0)
        elif name in ("left", "right"):
            strip.nudge((1.0 if shift else grid) * (1 if name == "right" else -1))
        elif name == "escape" and strip.session.selected:
            strip.clear_selection()
        else:
            return False
        return True

    # ------------------------------------------------------- user actions
    def on_record(self):
        if self.state == "recording":
            self.controller.stop_recording()
        else:
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

    def on_bass_style(self, text):
        if self.controller:
            self.controller.set_bass_style(BASS_STYLE_OPTIONS.get(text, "auto"))

    def on_drum_style(self, text):
        if self.controller:
            self.controller.set_drum_style(DRUM_STYLE_OPTIONS.get(text, "auto"))

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

    def _open_save_dialog(self, initialfile, title, save_action):
        if getattr(self, "_saving", False):
            return
        self._saving = True
        chooser = FileChooserListView(path=os.path.expanduser("~"), filters=["*.wav"])
        filename = TextInput(text=initialfile, multiline=False, size_hint_y=None, height=44)
        content = BoxLayout(orientation="vertical", spacing=8, padding=10)
        content.add_widget(chooser)
        content.add_widget(Label(text="File name", size_hint_y=None, height=24,
                                 halign="left", valign="middle"))
        content.add_widget(filename)
        actions = BoxLayout(size_hint_y=None, height=44, spacing=8)
        save_button = Button(text="Save")
        cancel_button = Button(text="Cancel")
        actions.add_widget(save_button)
        actions.add_widget(cancel_button)
        content.add_widget(actions)
        popup = Popup(title=title, content=content, size_hint=(0.82, 0.82), auto_dismiss=False)

        def close(*_):
            self._saving = False
            popup.dismiss()

        def save(*_):
            name = filename.text.strip()
            if not name:
                self.status_text = "Enter a file name to save"
                return
            if not name.lower().endswith(".wav"):
                name += ".wav"
            path = os.path.join(chooser.path, name)
            try:
                if save_action(path):
                    self.status_text = f"Saved {path}"
                else:
                    self.status_text = "Nothing to save yet"
            except Exception as exc:
                self.status_text = f"Save failed: {exc}"
            close()

        save_button.bind(on_release=save)
        cancel_button.bind(on_release=close)
        popup.bind(on_dismiss=lambda *_: setattr(self, "_saving", False))
        popup.open()
        self._save_popup = popup

    def on_save(self):
        if not self.controller:
            return
        self._open_save_dialog("hum2band.wav", "Save Backing Track", self.controller.save_wav)

    def on_play_reference(self):
        if self.controller and not self.controller.play_reference():
            self.status_text = "No hummed reference audio available"

    def on_reference_mix(self, enabled):
        self.reference_with_band = bool(enabled)
        if self.controller:
            self.controller.set_reference_mix(enabled)

    def on_save_reference(self):
        if not self.controller or not self.can_reference:
            return
        self._open_save_dialog("hummed_reference.wav", "Save Hummed Reference",
                               self.controller.save_reference_wav)
