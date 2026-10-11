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

## Test (no mic, speakers or Kivy needed)
```
pytest            # or: python run_tests.py
python render_demo.py   # demo melody -> demo_pop.wav / demo_lofi.wav
```

## Layout
`core/` has no Kivy imports (NFR-8): `models, patterns, analysis, generator, pitch,
audio_in, playback, controller`. `ui/` + `main.py` are the only Kivy code.

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
