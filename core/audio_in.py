"""Microphone capture + per-frame pitch estimation (no Kivy imports).

The sounddevice callback only copies samples into a queue. A worker thread
does the pitch analysis, so neither the audio callback nor the UI thread is
ever blocked (NFR-3).
"""
import math
import queue
import threading

import numpy as np

from .analysis import freq_to_midi
from .models import PitchFrame
from .pitch import HOP, SR, WIN, make_detector

NOISE_GATE_RMS = 0.01      # ~ -40 dBFS
CONF_THRESHOLD = 0.80


class MicError(Exception):
    pass


def refresh_portaudio():
    """Re-scan devices so OS-level changes (new default mic, plugged headset) are seen.
    Only safe while no streams are open."""
    try:
        import sounddevice as sd
        sd._terminate()
        sd._initialize()
    except Exception:
        pass


def list_devices(kind):
    """[(index, label, default_samplerate)] for 'input' or 'output' devices."""
    import sounddevice as sd
    apis = sd.query_hostapis()
    out = []
    for i, d in enumerate(sd.query_devices()):
        ch = d["max_input_channels"] if kind == "input" else d["max_output_channels"]
        if ch > 0:
            out.append((i, f"{i}: {d['name']} [{apis[d['hostapi']]['name']}]",
                        int(d["default_samplerate"])))
    return out


def candidate_rates(default_rate):
    return [default_rate] + [r for r in (48000, 44100) if r != default_rate]


def level_from_rms(rms: float) -> float:
    """Map RMS to a 0..1 meter value (-60 dBFS .. 0 dBFS)."""
    db = 20 * math.log10(max(rms, 1e-6))
    return min(1.0, max(0.0, (db + 60.0) / 60.0))


class MicRecorder:
    def __init__(self, on_frame=None, on_capture_done=None, sr=SR):
        self.sr = sr
        self.on_frame = on_frame
        self.on_capture_done = on_capture_done
        self.gate = NOISE_GATE_RMS
        self.conf_threshold = CONF_THRESHOLD
        self.gain = 1.0                    # software input gain
        self.detector = make_detector(True, sr)
        self.running = False
        self.device_name = ""
        self._q = queue.Queue()
        self._stream = None
        self._thread = None
        self._reset_worker_state()

    def _reset_worker_state(self):
        self._pending = np.zeros(0, dtype=np.float32)
        self._win = np.zeros(WIN, dtype=np.float32)
        self._total = 0
        self._capturing = False
        self._t0 = 0.0
        self._duration = 0.0
        self._frames = []

    # ---- lifecycle -------------------------------------------------
    def start(self, device=None):
        """Open `device` (index or None = system default) at a rate it supports."""
        self.stop()
        try:
            import sounddevice as sd
        except Exception as e:  # PortAudio missing, package missing...
            raise MicError(f"Audio library unavailable: {e}")
        try:
            info = sd.query_devices(device, "input")
        except Exception as e:
            raise MicError(f"No microphone available. Check your input device. ({e})")
        max_ch = max(1, int(info["max_input_channels"]))
        last = None
        for sr in candidate_rates(int(info["default_samplerate"])):
            for ch in (1, min(2, max_ch)):
                try:
                    stream = sd.InputStream(device=device, samplerate=sr, channels=ch,
                                            dtype="float32", blocksize=HOP,
                                            callback=self._callback)
                    stream.start()
                except Exception as e:
                    last = e
                    continue
                self._stream, self.sr, self.device_name = stream, sr, info["name"]
                self._begin_worker()
                return
        raise MicError(f"Could not open '{info['name']}' ({last}). "
                       "Pick another input device or check OS privacy/mic permissions.")

    def _begin_worker(self):
        self._reset_worker_state()
        self.detector = make_detector(True, self.sr)
        self._q = queue.Queue()            # fresh queue: old worker can't steal items
        self.running = True
        self._thread = threading.Thread(target=self._worker, args=(self._q,), daemon=True)
        self._thread.start()

    def stop(self):
        was = self.running
        self.running = False
        if was:
            self._q.put(None)
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    # ---- capture control (thread-safe: goes through the same queue) ----
    def begin_capture(self, duration_s):
        self._q.put(("begin", float(duration_s)))

    def cancel_capture(self):
        self._q.put(("cancel", 0.0))

    # ---- internals -------------------------------------------------
    def _callback(self, indata, frames, time_info, status):
        block = indata.mean(axis=1) if indata.shape[1] > 1 else indata[:, 0]
        if self.gain != 1.0:
            block = np.clip(block * self.gain, -1.0, 1.0)
        self._q.put(np.array(block, dtype=np.float32))

    def _worker(self, q):
        while True:
            try:
                item = q.get(timeout=0.25)
            except queue.Empty:
                if not self.running or q is not self._q:
                    return
                continue
            if item is None:
                return
            if isinstance(item, tuple):
                cmd, val = item
                if cmd == "begin":
                    self._capturing, self._frames = True, []
                    self._t0, self._duration = self._total / self.sr, val
                else:
                    self._capturing, self._frames = False, []
                continue
            self.feed(item)

    def feed(self, block):
        """Feed raw samples (also usable from tests without a device)."""
        self._pending = np.concatenate((self._pending, block.astype(np.float32)))
        while len(self._pending) >= HOP:
            chunk, self._pending = self._pending[:HOP], self._pending[HOP:]
            self._process_hop(chunk)

    def _process_hop(self, chunk):
        self._win = np.concatenate((self._win[HOP:], chunk))
        self._total += HOP
        rms = float(np.sqrt(np.mean(self._win[-1024:] ** 2)))
        midi, conf = None, 0.0
        if rms >= self.gate:
            freq, conf = self.detector.detect(self._win, chunk)
            if 60.0 < freq < 1100.0 and conf >= self.conf_threshold:
                midi = freq_to_midi(freq)
        t_abs = (self._total - WIN // 2) / self.sr
        if self.on_frame:
            self.on_frame(PitchFrame(t_abs, midi, rms, conf))
        if self._capturing:
            t = t_abs - self._t0
            if t >= 0:
                self._frames.append(PitchFrame(t, midi, rms, conf))
            if t >= self._duration:
                self._capturing = False
                frames, self._frames = self._frames, []
                if self.on_capture_done:
                    self.on_capture_done(frames)
