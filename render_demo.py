"""Headless check: demo melody -> key -> band -> WAV (no Kivy / mic / speakers needed)."""
import json
import os
import sys

from core.analysis import detect_key, quantize
from core.generator import chord_labels, generate
from core.models import Note
from core.patterns import NOTE_NAMES
from core.playback import mix, render_tracks, write_wav

here = os.path.dirname(os.path.abspath(__file__))
notes = [Note(**n) for n in json.load(open(os.path.join(here, "assets", "demo_melody.json")))["notes"]]
root, mode = detect_key(notes)
print(f"Detected key: {NOTE_NAMES[root]} {mode}")
out_dir = sys.argv[1] if len(sys.argv) > 1 else here
for genre, bpm in (("pop", 110), ("lo-fi", 80)):
    song = generate(quantize(notes, root, mode), root, mode, bpm, genre)
    print(f"{genre:6s} @ {bpm} BPM chords: {' '.join(chord_labels(song))}")
    path = os.path.join(out_dir, f"demo_{genre.replace('-', '')}.wav")
    write_wav(path, mix(render_tracks(song), genre))
    print("  wrote", path)
