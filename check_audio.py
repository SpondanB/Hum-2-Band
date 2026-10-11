"""Audio diagnostic:  python check_audio.py
Lists devices, shows which one the OS reports as default, tries to open the mic and
speakers the same way the app does, and prints a live input level for 4 seconds."""
import time

import numpy as np

try:
    import sounddevice as sd
except Exception as e:
    raise SystemExit(f"sounddevice/PortAudio not available: {e}\n"
                     "Linux: sudo apt install libportaudio2   |   then: pip install sounddevice")

from core.audio_in import MicError, MicRecorder, level_from_rms, list_devices
from core.playback import AudioEngine, click_buffer

print("Default devices (input, output):", sd.default.device)
for kind in ("input", "output"):
    print(f"\n{kind.upper()} devices:")
    for idx, label, rate in list_devices(kind):
        print(f"  {label}   default rate {rate} Hz")

print("\nOpening default microphone...")
levels = []
rec = MicRecorder(on_frame=lambda f: levels.append(f.rms))
try:
    rec.start()
    print(f"  OK: '{rec.device_name}' at {rec.sr} Hz")
    t_end = time.time() + 4
    print("  Speak/hum now. If the bar never moves: mic muted in OS settings, "
          "wrong input device, or no mic permission.")
    while time.time() < t_end:
        time.sleep(0.25)
        lv = level_from_rms(levels[-1]) if levels else 0
        print("  level |" + "#" * int(lv * 40) + " " * (40 - int(lv * 40)) + "|", end="\r")
    print("\n  peak RMS:", f"{max(levels, default=0):.4f}", "(gate is 0.01)")
    rec.stop()
except MicError as e:
    print("  FAILED:", e)

print("\nOpening default speakers and playing 4 clicks...")
eng = AudioEngine()
try:
    eng.start()
    print(f"  OK: '{eng.device_name}' at {eng.sr} Hz")
    eng.play_oneshot(click_buffer(120, sr=eng.sr))
    time.sleep(2.3)
    eng.stop_stream()
except Exception as e:
    print("  FAILED:", e)
