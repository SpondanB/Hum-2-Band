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
from .patterns import BASS_STYLES, DRUM_STYLES, GENRES
from .pitch import HOP
from .playback import (AudioEngine, click_buffer, mix, preview_tone, render_tracks,
                       write_wav)

DEMO_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "demo_melody.json")
BUSY_STATES = ("counting", "recording", "processing")
HISTORY_LIMIT = 100


class Controller:
    def __init__(self, on_state=None, on_live=None, on_result=None, bars=4):
        self._on_state = on_state or (lambda state, info: None)
        self._on_live = on_live or (lambda note, level: None)
        self._on_result = on_result or (lambda song: None)
        self.bars = bars
        self.bpm = 100
        self.genre = "pop"
        self.bass_style = "auto"
        self.drum_style = "auto"
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
        self.max_record_seconds = 45.0
        self.duration_beats = self.bars * 4.0
        self._build_lock = threading.Lock()
        self._audio_ok = False
        self.input_device = None          # None = system default
        self.output_device = None
        # --- melody editing
        self.snap_to_scale = True         # quantize the melody to the key (FR-7); off = free pitches
        self.edit_rev = 0                 # bumps on every melody change (record, edit, undo)
        self.built_rev = 0                # edit_rev that the current song was built from
        self.melody_gen = 0               # bumps only when a NEW melody is recognised/loaded
        self._undo, self._redo = [], []   # snapshots: (raw_notes, detected_key)
        self._preview_cache = {}

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
        if self.detected_key is not None:
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

    def set_max_record_seconds(self, seconds):
        self.max_record_seconds = max(5.0, min(45.0, float(seconds)))

    def shutdown(self):
        self.recorder.stop()
        self.engine.stop_stream()

    def _set_state(self, state, **info):
        self.state = state
        self._on_state(state, info)

    # -------------------------------------------------------- recording
    def record(self):
        """Count-in (3 beats) then capture until silence or the 45s UI cap. Also used as Retry."""
        if self.state in BUSY_STATES:
            return
        if not self.recorder.running and not self._open_mic():
            return
        self.engine.stop()
        self._rec_bpm = self.bpm
        self._set_state("counting", bpm=self._rec_bpm)
        self.engine.play_oneshot(click_buffer(self._rec_bpm, beats=3, sr=self.engine.sr),
                                 self._count_in_done)

    def _count_in_done(self):                       # audio thread: keep it light
        duration = float(self.max_record_seconds)
        self._set_state("recording", duration=duration, bpm=self._rec_bpm)
        self.recorder.begin_capture(duration, silence_timeout=1.2)

    def stop_recording(self):
        if self.state != "recording":
            return False
        self.recorder.stop_capture()
        return True

    def _on_capture_done(self, frames):             # recorder worker thread
        self._set_state("processing")
        threading.Thread(target=self._finish_recording, args=(frames,), daemon=True).start()

    def _finish_recording(self, frames):
        try:
            hop_s = HOP / self.recorder.sr
            active_frames = [frame for frame in frames if frame.rms >= self.recorder.gate]
            duration_seconds = min(
                self.max_record_seconds,
                max((frame.t + hop_s for frame in active_frames), default=0.0),
            )
            duration_beats = duration_seconds * self._rec_bpm / 60.0
            bars = max(1, int((duration_beats + 4.0 - 1e-9) // 4.0))
            notes = frames_to_notes(frames, self._rec_bpm, bars, hop_s=hop_s,
                                    duration_beats=duration_beats)
            self.process_notes(notes, duration_beats=duration_beats)
        except Exception as e:
            self._set_state("error", message=f"Something went wrong: {e}")

    def _on_frame(self, frame):
        name = midi_to_name(frame.midi) if frame.midi is not None else "--"
        self._on_live(name, level_from_rms(frame.rms))

    # ------------------------------------------------------ processing
    def process_notes(self, notes, autoplay=True, duration_beats=None):
        """Notes (in beats) -> key -> band. Returns False if nothing usable."""
        key = detect_key(notes)
        if key is None:
            self._set_state("error",
                            message="No notes detected. Hum a bit louder or closer to the mic.")
            return False
        self._push_undo()                          # re-recording is undoable
        self._redo.clear()
        self.duration_beats = float(duration_beats if duration_beats is not None
                        else self.bars * 4.0)
        self.raw_notes, self.detected_key = list(notes), key
        self.snap_to_scale = True                  # fresh hum/demo: recognition snaps to the key
        self.edit_rev += 1
        self.melody_gen += 1
        self._rebuild()
        if autoplay and self._audio_ok:
            self.engine.play()
            self._set_state("playing")
        else:
            self._set_state("ready")
        return True

    def _rebuild(self):
        with self._build_lock:                     # params read inside the lock
            if self.detected_key is None:
                return
            rev = self.edit_rev
            root, mode = self.key_override or self.detected_key
            if self.snap_to_scale:
                melody = quantize(self.raw_notes, root, mode)
            else:
                melody = [Note(n.midi, n.start, n.duration) for n in self.raw_notes]
            bars = max(1, int((self.duration_beats + 4.0 - 1e-9) // 4.0))
            song = generate(melody, root, mode, self.bpm, self.genre, bars,
                            duration_beats=self.duration_beats,
                            bass_style=self.bass_style, drum_style=self.drum_style)
            tracks = render_tracks(song, sr=self.engine.sr)
            self.song, self.tracks, self.built_rev = song, tracks, rev
            self.engine.set_loop(mix(tracks, song.genre, self.muted))
        self._on_result(song)

    def _rebuild_async(self):
        if self.detected_key is not None and self.state not in BUSY_STATES:
            threading.Thread(target=self._rebuild, daemon=True).start()

    # --------------------------------------------------------- settings
    def set_genre(self, genre):
        if genre in GENRES:
            self.genre = genre
            self._rebuild_async()

    def set_bass_style(self, style):
        if style in BASS_STYLES:
            self.bass_style = style
            self._rebuild_async()

    def set_drum_style(self, style):
        if style in DRUM_STYLES:
            self.drum_style = style
            self._rebuild_async()

    def set_tempo(self, bpm):
        self.bpm = int(max(60, min(160, bpm)))
        self._rebuild_async()

    def set_key_override(self, key):
        self.key_override = key
        if key is None and self.raw_notes:           # "Auto" = detect from the current melody
            self.detected_key = detect_key(self.raw_notes) or self.detected_key
        self._rebuild_async()

    def set_track_enabled(self, name, enabled):
        (self.muted.discard if enabled else self.muted.add)(name)
        if self.tracks and self.song:
            self.engine.set_loop(mix(self.tracks, self.song.genre, self.muted),
                                 mode="same_pos")

    # ------------------------------------------------------ melody editing
    @property
    def can_undo(self):
        return bool(self._undo)

    @property
    def can_redo(self):
        return bool(self._redo)

    def _snapshot(self):
        return ([Note(n.midi, n.start, n.duration) for n in self.raw_notes],
            self.detected_key, self.duration_beats)

    def _push_undo(self):
        if self.detected_key is None:
            return
        self._undo.append(self._snapshot())
        del self._undo[:-HISTORY_LIMIT]

    def _restore(self, snap):
        notes, key, duration_beats = snap
        self.raw_notes, self.detected_key = [Note(n.midi, n.start, n.duration) for n in notes], key
        self.duration_beats = duration_beats
        self.edit_rev += 1
        self._rebuild_async()
        return self.edit_rev

    def set_melody(self, notes):
        """Replace the melody with user-edited notes (in beats); the band follows.

        Returns the new edit revision, or None if editing isn't possible right now.
        The edited notes stay the source of truth, so Record / Demo can still replace
        them later (and Undo brings the old melody back).
        """
        if self.detected_key is None or self.state in BUSY_STATES:
            return None
        total = self.duration_beats
        clean = []
        for n in notes:
            start = min(max(0.0, float(n.start)), max(0.0, total - 0.05))
            dur = min(float(n.duration), max(0.0, total - start))
            if dur > 0:
                clean.append(Note(int(max(0, min(127, n.midi))), start, dur))
        self._push_undo()
        self._redo.clear()
        self.raw_notes = sorted(clean, key=lambda n: (n.start, n.midi))
        self.edit_rev += 1
        self._rebuild_async()
        return self.edit_rev

    def undo(self):
        if not self._undo or self.state in BUSY_STATES:
            return None
        self._redo.append(self._snapshot())
        return self._restore(self._undo.pop())

    def redo(self):
        if not self._redo or self.state in BUSY_STATES:
            return None
        self._undo.append(self._snapshot())
        return self._restore(self._redo.pop())

    def set_scale_lock(self, enabled):
        """Snap-to-key on/off. Turning it off keeps the notes exactly as displayed."""
        enabled = bool(enabled)
        if enabled == self.snap_to_scale:
            return
        if not enabled and self.song is not None:
            self.raw_notes = [Note(n.midi, n.start, n.duration) for n in self.song.melody]
        self.snap_to_scale = enabled
        self._rebuild_async()

    def preview_note(self, midi):
        """Audition a pitch over the running loop (no-op without audio output)."""
        if not self._audio_ok:
            return
        key = (int(midi), self.genre, self.engine.sr)
        buf = self._preview_cache.get(key)
        if buf is None:
            buf = self._preview_cache[key] = preview_tone(key[0], self.genre, self.engine.sr)
        self.engine.preview(buf)

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
