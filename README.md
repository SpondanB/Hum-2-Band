# Hum-to-Band
Hum 4 bars, get a full band. Python 3.10+, Kivy UI, desktop first.

## Run
```
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```
Tap **Record** -> 4-beat count-in -> hum 4 bars -> the band starts automatically.
No mic or noisy room? Tap **Demo melody**. Use a headset mic for the live demo.

First thing to check on every machine (needs PortAudio, bundled on Win/macOS wheels,
`sudo apt install libportaudio2` on Linux):
```
python -c "import kivy, sounddevice; print('ok')"
```

## Editing the melody
After a hum (or the demo) the melody appears on the piano roll and can be edited; the band
rebuilds from your edits and swaps in at the next loop. Recording again still works - it just
replaces the melody, and **Undo** brings the old one back.

| Do this | To get this |
|---|---|
| Click a note | select it (it plays a short preview) |
| Shift/Ctrl-click, or drag a box on empty space | select several notes |
| Drag a selected note | move **all** selected notes together (time snaps to the grid; pitch moves by scale steps) |
| Drag a note's right edge | resize all selected notes |
| Double-click empty space / a note | add a note / delete that note |
| Del, Up/Down, Left/Right | delete, transpose (scale step), nudge by one grid step |
| Shift + Up/Down, Shift + Left/Right | transpose an octave, nudge a whole beat |
| Ctrl+A, Ctrl+Z, Ctrl+Y (or Ctrl+Shift+Z), Esc | select all, undo, redo, deselect |
| Mouse wheel over the chart | scroll the pitch range |
| Click a key in the left gutter | hear that pitch |

The left gutter is a piano-key guide: note name + octave, the scale degree (1-7) of each
in-key row, the key's root in the accent colour, and a teal tick on every in-key row.
Black-key rows are shaded. **Snap to key** keeps edits inside the key (turn it off for
chromatic notes; those get a red top edge). **Grid** sets the snap for time (1/4, 1/8, 1/16).
Choosing **Key: Auto** re-detects the key from the melody as it is now.

## Audio troubleshooting
Run `python check_audio.py` first: it lists every input/output device, shows what the OS
reports as default, opens mic + speakers exactly like the app, and prints a live level meter.
- The app reads the OS default devices **at launch**. After changing the default mic/speakers
  (or plugging in a headset) click **Refresh audio**, or pick a device in the dropdowns.
- The app uses each device's native sample rate (44.1/48 kHz), mono or stereo.
- Level bar never moves: mic muted/low in OS settings, wrong input selected, or the OS
  mic privacy permission is off (Windows: Settings > Privacy > Microphone; macOS: allow
  your terminal/Python). Use **Mic gain** for quiet mics.
- To feed the app *system* audio (what your computer is playing) instead of a mic, pick a
  loopback device as the input: "Stereo Mix" (Windows), BlackHole/Loopback (macOS),
  a PulseAudio "Monitor of ..." source (Linux). The app has no built-in loopback capture.

## Test (no mic, speakers or Kivy needed)
```
pytest            # or: python run_tests.py
python render_demo.py   # demo melody -> demo_pop.wav / demo_lofi.wav
```

## Layout
`core/` has no Kivy imports (NFR-8): `models, patterns, analysis, generator, pitch,
audio_in, playback, controller, roll, editing` (`editing.EditSession` holds every
editing rule; `ui/note_strip.py` only draws it and forwards mouse events). `ui/` + `main.py` are the only Kivy code.

## How it works
- **Capture:** sounddevice callback only queues samples; a worker thread runs pitch
  detection (aubio YIN if installed, else NumPy YIN), noise gate + confidence gate.
- **Notes:** octave-glitch fold, median filter, merge within 0.5 semitone, drop < 100 ms,
  snap to 8th-note grid -> key detection (24 keys) -> quantize to scale.
- **Band:** one diatonic chord per bar (most melody overlap; ties -> I-V-vi-IV),
  root bass an octave below, 16-step drum grids per genre.
- **Playback:** the 4-bar loop is rendered to one integer-length buffer and the audio
  callback is the single master clock, so there is no drift. Genre/tempo/key changes
  are rebuilt in the background and swapped in at the next loop boundary.

## Tuning knobs
`core/audio_in.py`: `NOISE_GATE_RMS`, `CONF_THRESHOLD`. `core/patterns.py`: drum grids,
progressions, track gains.

## Not done / known limits
Android (sounddevice doesn't run there), PyInstaller packaging, input device selection
(uses the system default), 44.1 kHz assumed.

## Responsive layout
The window can be any size; nothing is cut off.
- **Wide windows (roughly 860 dp and up, landscape):** the piano roll takes the left side and the
  secondary settings (band, mix, hum reference, audio, tips) sit in a scrolling panel on the right.
- **Narrow / tall windows:** the roll is on top (it never drops below a minimum height) and the
  settings scroll underneath.
- **Always visible:** Record / Play / Demo / Save and the live note + level meter.
- **Scale:** one UI scale (0.85x to 1.6x) follows the window size, so a 4K monitor or tablet is as
  comfortable as a laptop. Layout and scale rules are in `ui/responsive.py` (unit-tested).
- **Piano roll:** keeps every pitch row readable for the available height; scroll the rest with the
  mouse wheel or by dragging the piano keys (works on touch screens too).
- Minimum window size is 400x480. The default window is 1000x680 so it fits a 1366x768 laptop.
