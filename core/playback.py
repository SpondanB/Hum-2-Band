"""Synth, mixer and looping playback engine (no Kivy imports).

Timing: the whole 4-bar loop is rendered into one integer-length buffer and
the audio callback just reads it with wrap-around. The callback is the single
master clock, so tempo cannot drift (NFR-4). Changes (genre/tempo) are swapped
in at the next loop boundary.
"""
import wave

import numpy as np

from .patterns import DRUMS, DRUM_GROOVES, TRACK_GAINS, TRACKS

SR = 44100


# ---------------------------------------------------------------- synthesis
def _mtof(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def _tone(freq, dur, harmonics, attack=0.01, release=0.08, decay=0.0, sr=SR):
    n = int((dur + release) * sr)
    t = np.arange(n) / sr
    w = np.zeros(n)
    for k, a in enumerate(harmonics, 1):
        if freq * k < sr / 2:
            w += a * np.sin(2 * np.pi * freq * k * t)
    w /= sum(harmonics)
    env = np.minimum(t / attack, 1.0)
    env *= np.where(t > dur, np.clip(1 - (t - dur) / release, 0, 1), 1.0)
    if decay:
        env *= np.exp(-decay * t)
    return (w * env).astype(np.float32)


VOICES = {
    "pop": {
        "melody": dict(harmonics=[1, .5, .33, .25, .2, .16], decay=0.3),
        "chords": dict(harmonics=[1, .4, .2], decay=0.6, attack=0.02),
        "bass": dict(harmonics=[1, .5, .15], decay=0.5),
    },
    "lo-fi": {
        "melody": dict(harmonics=[1, .3, .1], decay=1.2),
        "chords": dict(harmonics=[1, .15], decay=0.9, attack=0.04),
        "bass": dict(harmonics=[1, .25], decay=0.8),
    },
    "rock": {
        "melody": dict(harmonics=[1, .65, .45, .3, .2], decay=0.22),
        "chords": dict(harmonics=[1, .65, .35, .2], decay=0.35, attack=0.008),
        "bass": dict(harmonics=[1, .65, .3], decay=0.28),
    },
    "funk": {
        "melody": dict(harmonics=[1, .35, .12], decay=0.45),
        "chords": dict(harmonics=[1, .22], decay=1.0, attack=0.004),
        "bass": dict(harmonics=[1, .35, .08], decay=1.4, attack=0.004),
    },
    "hip-hop": {
        "melody": dict(harmonics=[1, .2, .08], decay=0.75),
        "chords": dict(harmonics=[1, .2], decay=0.7, attack=0.025),
        "bass": dict(harmonics=[1, .12], decay=0.65, attack=0.004),
    },
    "electronic": {
        "melody": dict(harmonics=[1, .45, .2, .1], decay=0.55),
        "chords": dict(harmonics=[1, .3, .08], decay=1.1, attack=0.012),
        "bass": dict(harmonics=[1, .08], decay=0.4, attack=0.003),
    },
}


def _add(buf, start, wave_):
    """Mix wave_ into buf at sample `start`, wrapping the tail to the loop start."""
    n = len(buf)
    start %= n
    end = start + len(wave_)
    if end <= n:
        buf[start:end] += wave_
    else:
        k = n - start
        buf[start:] += wave_[:k]
        rest = wave_[k:]
        buf[:len(rest)] += rest


def _drum_samples(rng, sr=SR):
    t = np.arange(int(0.25 * sr)) / sr
    phase = 2 * np.pi * (45 * t + 75 * (1 - np.exp(-30 * t)) / 30)
    kick = np.sin(phase) * np.exp(-t * 18)
    ts = t[:int(0.2 * sr)]
    snare = (rng.uniform(-1, 1, len(ts)) * np.exp(-ts * 25) * 0.7
             + 0.5 * np.sin(2 * np.pi * 180 * ts) * np.exp(-ts * 30))
    th = t[:int(0.05 * sr)]
    noise = rng.uniform(-1, 1, len(th) + 1)
    hat = np.diff(noise) * np.exp(-th * 80) * 0.5      # crude high-pass
    return {"kick": kick.astype(np.float32), "snare": snare.astype(np.float32),
            "hat": hat.astype(np.float32)}


def render_tracks(song, sr=SR):
    """Render each track into its own loop-length mono buffer."""
    beat_s = 60.0 / song.bpm
    duration_beats = song.duration_beats if song.duration_beats is not None else song.bars * 4
    n = int(round(duration_beats * beat_s * sr))
    pos = lambda beats: int(round(beats * beat_s * sr))
    voices = VOICES[song.genre]
    tracks = {name: np.zeros(n, dtype=np.float32) for name in TRACKS}

    for name, notes in (("melody", song.melody), ("chords", song.chords), ("bass", song.bass)):
        cache = {}
        for note in notes:
            key = (note.midi, note.duration)
            if key not in cache:
                cache[key] = _tone(_mtof(note.midi), note.duration * beat_s, sr=sr,
                                   **voices[name])
            _add(tracks[name], pos(note.start), cache[key])

    rng = np.random.default_rng(7)             # fixed seed -> deterministic loop
    samples = _drum_samples(rng, sr)
    pattern = DRUM_GROOVES.get(song.drum_style, DRUMS[song.genre])
    for bar in range(song.bars):
        for inst, grid in pattern.items():
            for i, vel in enumerate(grid):
                beat = bar * 4 + i / 4.0
                if not vel or beat >= duration_beats:
                    continue
                amp = vel
                if inst == "kick":
                    amp *= 1.0 + 0.25 * (bar % 2 == 0)
                elif inst == "snare":
                    amp *= 1.0 + 0.35 * ((bar + i) % 8 == 4)
                elif inst == "hat":
                    amp *= 1.0 + 0.2 * ((bar + i) % 2 == 1)
                if amp > 0:
                    _add(tracks["drums"], pos(beat), samples[inst] * amp)
    return tracks


def mix(tracks, genre, muted=()):
    out = np.zeros_like(next(iter(tracks.values())))
    for name, buf in tracks.items():
        if name not in muted:
            out += buf * TRACK_GAINS[name]
    if genre == "lo-fi":   # circular moving average = gentle low-pass, loop-safe
        out = (out + np.roll(out, 1) + np.roll(out, 2) + np.roll(out, 3)) / 4.0
    return (np.tanh(out * 1.2) * 0.9).astype(np.float32)


def preview_tone(midi, genre="pop", sr=SR, dur=0.35):
    """Short melody-voice blip used to audition a pitch while editing."""
    voice = VOICES.get(genre, VOICES["pop"])["melody"]
    return (_tone(_mtof(midi), dur, sr=sr, **voice) * 1.6 * TRACK_GAINS["melody"]).astype(np.float32)


def click_buffer(bpm, beats=3, sr=SR):
    beat_n = int(round(60.0 / bpm * sr))
    buf = np.zeros(beat_n * beats, dtype=np.float32)
    t = np.arange(int(0.04 * sr)) / sr
    for b in range(beats):
        f = 2000.0 if b == 0 else 1400.0
        buf[b * beat_n:b * beat_n + len(t)] += (np.sin(2 * np.pi * f * t)
                                                * np.exp(-t * 90) * 0.6).astype(np.float32)
    return buf


def write_wav(path, data, sr=SR):
    pcm = (np.clip(data, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


# ------------------------------------------------------------------ engine
class AudioEngine:
    def __init__(self, sr=SR):
        self.sr = sr
        self.device_name = ""
        self._stream = None
        self._loop = None
        self._pending = None
        self._pos = 0
        self.playing = False
        self._oneshot = None
        self._os_pos = 0
        self._os_done = None
        self._preview = None
        self._pv_pos = 0

    def start(self, device=None):
        """Open `device` (index or None = system default) at a rate it supports."""
        import sounddevice as sd
        self.stop_stream()
        info = sd.query_devices(device, "output")
        max_ch = max(1, int(info["max_output_channels"]))
        default = int(info["default_samplerate"])
        last = None
        for sr in [default] + [r for r in (48000, 44100) if r != default]:
            for ch in (1, min(2, max_ch)):
                for latency in ("low", "high"):
                    try:
                        stream = sd.OutputStream(device=device, samplerate=sr, channels=ch,
                                                 dtype="float32", blocksize=512,
                                                 latency=latency, callback=self._callback)
                        stream.start()
                    except Exception as e:
                        last = e
                        continue
                    self._stream, self.sr, self.device_name = stream, sr, info["name"]
                    return
        raise RuntimeError(f"Could not open output '{info['name']}': {last}")

    def stop_stream(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    # -- control
    def set_loop(self, buf, mode="next_loop"):
        """mode: 'next_loop' swap at boundary, 'same_pos' swap now if same length."""
        if self._loop is None or not self.playing:
            self._loop, self._pending, self._pos = buf, None, 0
        elif mode == "same_pos" and len(buf) == len(self._loop):
            self._loop = buf
        else:
            self._pending = buf

    def play(self):
        if self._pending is not None:
            self._loop, self._pending = self._pending, None
        self._pos = 0
        self.playing = self._loop is not None

    def stop(self):
        self.playing = False

    def play_oneshot(self, buf, on_done=None):
        self.playing = False
        self._os_pos, self._os_done, self._oneshot = 0, on_done, buf

    def preview(self, buf):
        """Mix a short sound on top of whatever is playing (does not stop the loop)."""
        self._pv_pos = 0
        self._preview = buf

    def fraction(self):
        loop = self._loop
        if loop is None or not self.playing:
            return None
        return self._pos / len(loop)

    # -- audio thread
    def _callback(self, outdata, frames, time_info, status):
        out = np.zeros(frames, dtype=np.float32)
        self._fill(out, frames)
        pv = self._preview
        if pv is not None:
            chunk = pv[self._pv_pos:self._pv_pos + frames]
            out[:len(chunk)] += chunk
            self._pv_pos += frames
            if self._pv_pos >= len(pv):
                self._preview = None
        outdata[:] = out[:, None]            # mono -> every output channel

    def _fill(self, out, frames):
        shot = self._oneshot
        if shot is not None:
            chunk = shot[self._os_pos:self._os_pos + frames]
            out[:len(chunk)] = chunk
            self._os_pos += frames
            if self._os_pos >= len(shot):
                self._oneshot, cb, self._os_done = None, self._os_done, None
                if cb:
                    cb()
            return
        loop = self._loop
        if not self.playing or loop is None:
            return
        filled = 0
        while filled < frames:
            n = min(frames - filled, len(loop) - self._pos)
            out[filled:filled + n] = loop[self._pos:self._pos + n]
            filled += n
            self._pos += n
            if self._pos >= len(loop):
                self._pos = 0
                if self._pending is not None:
                    loop, self._loop, self._pending = self._pending, self._pending, None
