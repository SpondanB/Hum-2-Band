"""Workflow controller: record -> process -> play. No Kivy imports.

All callbacks may fire from non-UI threads; the UI layer must marshal them
onto the Kivy thread (see ui/screens.py).
"""
import json
import os
import threading

from .analysis import detect_key, frames_to_notes, midi_to_name, quantize
from .audio_in import (MicError, MicRecorder, level_from_rms, list_devices,
                       refresh_portaudio)
from .generator import chord_labels, generate
from .models import Note
from .pitch import HOP
from .playback import AudioEngine, click_buffer, mix, render_tracks, write_wav

DEMO_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "demo_melody.json")
BUSY_STATES = ("counting", "recording", "processing")


class Controller:
    def __init__(self, on_state=None, on_live=None, on_result=None, bars=4):
        self._on_state = on_state or (lambda state, info: None)
        self._on_live = on_live or (lambda note, level: None)
        self._on_result = on_result or (lambda song: None)
        self.bars = bars
        self.bpm = 100
        self.genre = "pop"
        self.key_override = None          # (root, mode) or None
        self.detected_key = None
        self.raw_notes = []               # unquantized-to-key notes, in beats
        self.song = None
        self.tracks = None
        self.muted = set()
        self.state = "idle"
        self.engine = AudioEngine()
        self.recorder = MicRecorder(on_frame=self._on_frame,
                                    on_capture_done=self._on_capture_done)
        self._rec_bpm = self.bpm
        self._build_lock = threading.Lock()
        self._audio_ok = False
        self.input_device = None          # None = system default
        self.output_device = None

    # ------------------------------------------------------------ setup
    def start(self):
        self._open_output()
        self._open_mic()

    def _open_output(self):
        try:
            self.engine.start(self.output_device)
            self._audio_ok = True
        except Exception as e:
            self._audio_ok = False
            self._set_state("error", message=f"Audio output unavailable: {e}")
            return False
        if self.raw_notes:
            self._rebuild()                      # re-render at the device's sample rate
        return True

    def _open_mic(self):
        try:
            self.recorder.start(self.input_device)
        except MicError as e:
            self._set_state("error", message=str(e))
            return False
        self._set_state("ready" if self.song else "idle")
        return True

    # ------------------------------------------------------ devices
    def list_devices(self):
        """(inputs, outputs): lists of (index, label, default_rate)."""
        try:
            return list_devices("input"), list_devices("output")
        except Exception:
            return [], []

    def restart_audio(self):
        """Re-scan OS devices/defaults and reopen both streams (the Refresh button)."""
        if self.state in BUSY_STATES:
            return
        self.recorder.stop()
        self.engine.stop_stream()
        self.engine.stop()
        refresh_portaudio()
        ins, outs = self.list_devices()
        if self.input_device not in [d[0] for d in ins]:
            self.input_device = None
        if self.output_device not in [d[0] for d in outs]:
            self.output_device = None
        self.start()

    def set_input_device(self, index):
        self.input_device = index
        if self.state not in BUSY_STATES:
            self._open_mic()

    def set_output_device(self, index):
        self.output_device = index
        if self.state not in BUSY_STATES:
            was_playing = self.engine.playing
            if self._open_output() and was_playing:
                self.play()

    def set_input_gain(self, gain):
        self.recorder.gain = float(gain)

    def shutdown(self):
        self.recorder.stop()
        self.engine.stop_stream()

    def _set_state(self, state, **info):
        self.state = state
        self._on_state(state, info)

    # -------------------------------------------------------- recording
    def record(self):
        """Count-in (4 beats) then record exactly `bars` bars. Also used as Retry."""
        if self.state in BUSY_STATES:
            return
        if not self.recorder.running and not self._open_mic():
            return
        self.engine.stop()
        self._rec_bpm = self.bpm
        self._set_state("counting", bpm=self._rec_bpm)
        self.engine.play_oneshot(click_buffer(self._rec_bpm, sr=self.engine.sr), self._count_in_done)

    def _count_in_done(self):                       # audio thread: keep it light
        duration = self.bars * 4 * 60.0 / self._rec_bpm
        self._set_state("recording", duration=duration, bpm=self._rec_bpm)
        self.recorder.begin_capture(duration)

    def _on_capture_done(self, frames):             # recorder worker thread
        self._set_state("processing")
        threading.Thread(target=self._finish_recording, args=(frames,), daemon=True).start()

    def _finish_recording(self, frames):
        try:
            notes = frames_to_notes(frames, self._rec_bpm, self.bars, hop_s=HOP / self.recorder.sr)
            self.process_notes(notes)
        except Exception as e:
            self._set_state("error", message=f"Something went wrong: {e}")

    def _on_frame(self, frame):
        name = midi_to_name(frame.midi) if frame.midi is not None else "--"
        self._on_live(name, level_from_rms(frame.rms))

    # ------------------------------------------------------ processing
    def process_notes(self, notes, autoplay=True):
        """Notes (in beats) -> key -> band. Returns False if nothing usable."""
        key = detect_key(notes)
        if key is None:
            self._set_state("error",
                            message="No notes detected. Hum a bit louder or closer to the mic.")
            return False
        self.raw_notes, self.detected_key = list(notes), key
        self._rebuild()
        if autoplay and self._audio_ok:
            self.engine.play()
            self._set_state("playing")
        else:
            self._set_state("ready")
        return True

    def _rebuild(self):
        with self._build_lock:                     # params read inside the lock
            if not self.raw_notes:
                return
            root, mode = self.key_override or self.detected_key
            melody = quantize(self.raw_notes, root, mode)
            song = generate(melody, root, mode, self.bpm, self.genre, self.bars)
            tracks = render_tracks(song, sr=self.engine.sr)
            self.song, self.tracks = song, tracks
            self.engine.set_loop(mix(tracks, song.genre, self.muted))
        self._on_result(song)

    def _rebuild_async(self):
        if self.raw_notes and self.state not in BUSY_STATES:
            threading.Thread(target=self._rebuild, daemon=True).start()

    # --------------------------------------------------------- settings
    def set_genre(self, genre):
        self.genre = genre
        self._rebuild_async()

    def set_tempo(self, bpm):
        self.bpm = int(max(60, min(160, bpm)))
        self._rebuild_async()

    def set_key_override(self, key):
        self.key_override = key
        self._rebuild_async()

    def set_track_enabled(self, name, enabled):
        (self.muted.discard if enabled else self.muted.add)(name)
        if self.tracks and self.song:
            self.engine.set_loop(mix(self.tracks, self.song.genre, self.muted),
                                 mode="same_pos")

    # --------------------------------------------------------- playback
    def play(self):
        if self.song is None or not self._audio_ok:
            return
        self.engine.play()
        self._set_state("playing")

    def stop(self):
        self.engine.stop()
        self._set_state("ready" if self.song else "idle")

    def playhead_beats(self):
        frac = self.engine.fraction()
        return None if frac is None else frac * self.bars * 4

    # ------------------------------------------------------ demo / export
    def load_demo(self):
        if self.state in BUSY_STATES:
            return
        with open(DEMO_PATH) as f:
            data = json.load(f)
        self.engine.stop()
        self.process_notes([Note(**n) for n in data["notes"]])

    def save_wav(self, path):
        if self.tracks is None or self.song is None:
            return False
        write_wav(path, mix(self.tracks, self.song.genre, self.muted), sr=self.engine.sr)
        return True

    def key_text(self):
        if self.song is None:
            return "Key: --"
        from .patterns import NOTE_NAMES
        txt = f"Key: {NOTE_NAMES[self.song.key_root]} {self.song.mode}"
        return txt + (" (manual)" if self.key_override else "")

    def chords_text(self):
        return "  ".join(chord_labels(self.song)) if self.song else ""
