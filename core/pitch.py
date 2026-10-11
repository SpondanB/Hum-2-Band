"""Pitch detectors: aubio YIN (preferred) or a pure-NumPy YIN fallback."""
import numpy as np

SR = 44100
WIN = 2048
HOP = 512


class YinDetector:
    """Pure NumPy YIN (FFT-based difference function)."""

    def __init__(self, sr=SR, fmin=70.0, fmax=1000.0, threshold=0.15):
        self.sr, self.fmin, self.fmax, self.threshold = sr, fmin, fmax, threshold
        self.name = "numpy-yin"

    def detect(self, window, hop=None):
        x = np.asarray(window, dtype=np.float64)
        n = len(x)
        tau_max = min(int(self.sr / self.fmin), n // 2)
        tau_min = max(2, int(self.sr / self.fmax))
        w = n - tau_max
        cs = np.concatenate(([0.0], np.cumsum(x * x)))
        e1 = cs[w]
        if e1 < 1e-9:
            return 0.0, 0.0
        e2 = cs[w:w + tau_max] - cs[0:tau_max]
        size = 1 << int(np.ceil(np.log2(n + w)))
        cross = np.fft.irfft(np.conj(np.fft.rfft(x[:w], size)) * np.fft.rfft(x, size),
                             size)[:tau_max]
        d = e1 + e2 - 2.0 * cross
        d[0] = 0.0
        cm = np.ones(tau_max)
        cum = np.cumsum(d[1:])
        cm[1:] = d[1:] * np.arange(1, tau_max) / np.maximum(cum, 1e-12)

        tau, t = None, tau_min
        while t < tau_max - 1:
            if cm[t] < self.threshold:
                while t + 1 < tau_max - 1 and cm[t + 1] < cm[t]:
                    t += 1
                tau = t
                break
            t += 1
        if tau is None:
            tau = int(np.argmin(cm[tau_min:tau_max - 1])) + tau_min
        conf = float(1.0 - cm[tau])

        shift = 0.0
        if 1 <= tau < tau_max - 1:
            a, b, c = cm[tau - 1], cm[tau], cm[tau + 1]
            denom = a - 2 * b + c
            if abs(denom) > 1e-12:
                shift = float(np.clip(0.5 * (a - c) / denom, -1, 1))
        return self.sr / (tau + shift), conf


class AubioDetector:
    def __init__(self, sr=SR, win=WIN, hop=HOP):
        import aubio  # may be missing
        self._p = aubio.pitch("yin", win, hop, sr)
        self._p.set_unit("Hz")
        self.name = "aubio-yin"

    def detect(self, window, hop):
        chunk = np.ascontiguousarray(hop, dtype=np.float32)
        return float(self._p(chunk)[0]), float(self._p.get_confidence())


def make_detector(prefer_aubio=True, sr=SR):
    if prefer_aubio:
        try:
            return AubioDetector(sr)
        except Exception:
            pass
    return YinDetector(sr)
