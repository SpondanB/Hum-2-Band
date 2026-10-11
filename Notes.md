# Hum-to-Band: Project Requirements Document

**Platform:** Python 3.10+ with Kivy (desktop first, Android as a stretch goal) **Build window:** 6-hour hackathon build, 2 to 3 people **Version:** 1.0

## 1. Overview

Hum-to-Band is an application where the user hums or sings a short melody into the microphone, and the app turns it into a cleaned-up melody in a detected musical key, then automatically plays it back with chords, a bass line and drums.

**One-line pitch:** Hum 4 bars, get a full band.

## 2. Goals and Scope

### 2.1 Goals

- Deliver one complete, reliable loop: **record hum, then detect notes, detect key, generate chords, bass and drums, then play back**.
- Be demo-ready: a judge can hum into a laptop and hear a result within about 10 seconds.
- Keep the architecture modular so audio logic can be built and tested without the UI.

### 2.2 In scope (MVP)

- Microphone recording of a 4-bar phrase with a metronome count-in.
- Real-time pitch detection and note segmentation.
- Quantization to the best-fitting major or minor scale and key detection.
- Rule-based chord, bass and drum generation.
- Two genres (Pop, Lo-fi), a tempo slider, play/stop and re-record.
- A simple note-strip visualization.

### 2.3 Out of scope (cut for time)

- Mixer with per-track volume, loop layering, audio export.
- More than two genres, MIDI export, user accounts, cloud features.
- Full noise-robust detection (use a headset mic or quiet corner for the demo).

## 3. Users and Scenarios

| User | Scenario |
| --- | --- |
| Casual user / judge | Opens the app, taps Record, hums a tune, hears a full band version. |
| Hobby musician | Uses it as a quick idea sketchpad, changes genre and tempo and replays. |

**Primary flow:** Launch, then Record (count-in, 4 bars), then Processing (under 2 s), then Result (note strip plus playback), then change genre or tempo and replay, or re-record.

## 4. Functional Requirements

Priority: **M** = must have, **S** = should have, **C** = could have.

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-1 | The app requests and opens the default microphone input and shows an error message if none is available. | M |
| FR-2 | The app shows the live detected note name (for example "A3") and a level meter while the mic is active. | M |
| FR-3 | The user can start a recording with one button. A metronome count-in of 4 beats plays first, then the app records exactly 4 bars at the chosen tempo. | M |
| FR-4 | The app estimates pitch per audio frame and discards frames below a confidence threshold or volume threshold (noise gate). | M |
| FR-5 | The app converts the pitch stream into discrete notes: merges adjacent frames of the same pitch, drops notes shorter than about 100 ms, and snaps timing to an 8th-note grid. | M |
| FR-6 | The app detects the most likely key (24 major and minor keys) by scoring the notes against each scale. | M |
| FR-7 | The app quantizes each note to the nearest note in the detected scale. | M |
| FR-8 | The app generates one chord per bar chosen from the key's diatonic chords (I, ii, iii, IV, V, vi), picking the chord containing the most melody notes. | M |
| FR-9 | The app generates a bass line using chord root notes (one or two notes per bar). | M |
| FR-10 | The app plays a drum pattern selected by genre (Pop, Lo-fi), synchronized to the tempo. | M |
| FR-11 | The app plays the cleaned melody, chords, bass and drums together in a looping playback, with Play/Stop controls. | M |
| FR-12 | The user can change genre and tempo (60 to 160 BPM) and hear the change on the next loop or restart without re-recording. | M |
| FR-13 | The app displays the cleaned melody as a note strip or simple piano roll, with a moving playhead during playback. | S |
| FR-14 | The user can manually override the detected key from a dropdown. | S |
| FR-15 | A built-in demo melody can be loaded without using the mic (fallback if the room is too loud). | S |
| FR-16 | Toggle individual tracks (melody, chords, bass, drums) on or off during playback. | C |
| FR-17 | Save the result as a WAV file. | C |
| FR-18 | The melody on the piano roll can be edited on screen: move notes in time and pitch, resize them, add notes (double-click) and delete notes. The band regenerates from the edited melody. | S |
| FR-19 | Several notes can be selected at once (Shift/Ctrl-click or a drag box) and moved, resized, transposed, nudged or deleted together, like a MIDI editor. | S |
| FR-20 | Hum recognition is unchanged: Record / Demo still produce a melody that can then be edited, and Undo/Redo restore earlier melodies, including the one before a re-record. | S |
| FR-21 | A piano-key guide on the left of the chart shows note names with octave, scale degrees, the key root and in-key / out-of-key rows. Edits can snap to the key (move by scale steps) and to a 1/4, 1/8 or 1/16 grid. | S |

## 5. Non-Functional Requirements

| ID | Requirement |
| --- | --- |
| NFR-1 | **Latency:** live note display updates in under 100 ms from the sound. |
| NFR-2 | **Processing time:** from end of recording to playback ready in under 2 seconds. |
| NFR-3 | **Responsiveness:** audio processing never blocks the Kivy UI thread (use a separate thread or callback). |
| NFR-4 | **Timing accuracy:** playback must keep steady tempo with no audible drift across a loop. |
| NFR-5 | **Reliability:** the app must not crash if the mic is silent, the room is noisy or no notes are detected. It should show a friendly message instead. |
| NFR-6 | **Usability:** the main flow should be completable with 2 taps and no instructions. |
| NFR-7 | **Portability:** runs on Windows, macOS and Linux. Android is a stretch goal. |
| NFR-8 | **Maintainability:** audio and music logic have no Kivy imports, so they can be unit tested on their own. |

## 6. Technology Stack

| Area | Choice | Notes |
| --- | --- | --- |
| Language | Python 3.10+ |  |
| UI framework | Kivy 2.x | Use KV language files for layout. |
| Mic capture | `sounddevice` (PortAudio) | Kivy has no built-in microphone recording API, so a separate library is required. |
| Pitch detection | `aubio` (YIN) as the primary option. Fallback: your own autocorrelation or YIN with NumPy. | Avoid heavy ML models (CREPE) for a 6-hour build. |
| Audio synthesis and playback | NumPy-generated waveforms (sine, saw, noise for drums) played through `sounddevice` | Kivy's built-in `SoundLoader` is not suited to precise timing. A small custom mixer is more reliable. |
| Music logic | Plain Python (`dataclasses`, no extra libraries) | Scales, chords, patterns. |
| Visualization | Kivy `canvas` instructions (Rectangle, Line) | Draw the note strip directly. |
| Packaging | PyInstaller for desktop. Buildozer for Android (stretch). | Check library support for Android early, because `sounddevice` does not run on Android. |
| Testing | `pytest` for music logic |  |

**Important platform note:** Build and demo on desktop first. The mic and audio libraries above are desktop libraries. An Android build would need a different capture path (for example `plyer` or `pyjnius` with Android's AudioRecord) and should only be attempted if the desktop version is done early.

## 7. System Architecture

The app is split into layers. Only the UI layer imports Kivy.

1. **UI layer (Kivy):** screens, buttons, note strip, sliders.
2. **Controller:** coordinates the workflow (record, process, play) and holds app state.
3. **Audio input module:** opens the mic stream and feeds frames to the pitch detector.
4. **Analysis module:** note segmentation, key detection and quantization.
5. **Generation module:** chords, bass and drum patterns.
6. **Playback engine:** schedules and mixes notes into an audio output stream with a looping clock.

**Threading model:** the sounddevice callback handles audio on its own thread. Results are passed to the UI through `kivy.clock.Clock.schedule_once` or a thread-safe queue. Never touch widgets from the audio thread.

## 8. Shared Data Formats

Agree on these first so team members can work in parallel.

```python
@dataclass
class Note:
    midi: int        # e.g. 60 = C4
    start: float     # in beats from start of loop
    duration: float  # in beats

@dataclass
class Song:
    key_root: int       # 0 to 11 (C = 0)
    mode: str           # "major" or "minor"
    bpm: int
    bars: int           # 4 for MVP
    melody: list[Note]
    chords: list[Note]  # one chord per bar, stored as stacked notes
    bass: list[Note]
    genre: str          # "pop" or "lo-fi"
```

Drum patterns are stored as 16-step grids per instrument, for example: `{"kick": [1,0,0,0, 0,0,0,0, 1,0,0,0, 0,0,0,0], "snare": [...], "hat": [...]}`

## 9. Key Algorithms

### 9.1 Pitch to notes

1. Read audio in frames (for example 2048 samples at 44.1 kHz, hop size of 512).
2. Run pitch detection per frame and convert frequency to MIDI note with `midi = 69 + 12*log2(f/440)`.
3. Drop frames with low confidence or low volume.
4. Merge consecutive frames within half a semitone into one note, and remove notes shorter than about 100 ms.
5. Snap start times and durations to an 8th-note grid.

### 9.2 Key detection

For each of the 24 keys, count how many melody notes (weighted by duration) fall inside that key's scale. Add a small bonus if the first or last note equals the tonic. Choose the highest-scoring key.

### 9.3 Quantization

Move any note not in the scale to the nearest scale note (prefer moving down on ties).

### 9.4 Chord selection

For each bar, score every diatonic triad (I, ii, iii, IV, V, vi) by the total duration of melody notes that belong to it. Choose the best. Break ties in favor of I, IV and V. Avoid repeating the same chord four times when scores are equal by preferring a common progression (for example I-V-vi-IV).

### 9.5 Bass and drums

Bass plays the chord root one octave below the chord, on beat 1 (and beat 3 for Lo-fi). Drums come from stored pattern tables per genre.

## 10. User Interface Requirements

### 10.1 Main screen layout

- **Top bar:** app name and key display (for example "Key: A minor").
- **Center:** large note strip or piano roll showing the melody, with a playhead.
- **Live indicator:** current detected note and mic level meter.
- **Controls row:** big **Record** button, **Play/Stop** button, **Re-record** button.
- **Settings row:** genre selector (Pop / Lo-fi), tempo slider (60 to 160 BPM), key override dropdown.

### 10.2 States

| State | UI behavior |
| --- | --- |
| Idle | Record enabled, Play disabled. |
| Counting in | Show "1, 2, 3, 4" large on screen. |
| Recording | Red indicator, progress bar over 4 bars, live note shown. |
| Processing | Short "Building your band..." message. |
| Ready / Playing | Note strip visible, playhead moving, Play/Stop enabled. |
| Error | Clear message (no mic, nothing detected) with a Retry button. |

### 10.3 Visual style

Dark background, one accent color, large touch-friendly buttons (at least 48 px high), readable from a few meters away for demo.

## 11. Suggested Project Structure

```
hum_to_band/
  main.py                 # Kivy App entry point
  ui/
    hum.kv                # layout
    screens.py            # widgets and screen logic
    note_strip.py         # custom canvas widget
  core/
    audio_in.py           # mic stream and pitch frames
    analysis.py           # segmentation, key detection, quantizing
    generator.py          # chords, bass, drums
    playback.py           # synth and mixer engine
    models.py             # Note and Song dataclasses
    patterns.py           # genre drum tables and progressions
  assets/
    demo_melody.json
  tests/
    test_analysis.py
    test_generator.py
  requirements.txt
  README.md
```

## 12. Dependencies (requirements.txt)

```
kivy>=2.2
numpy
sounddevice
aubio
pytest
```

If `aubio` fails to install on a teammate's machine, switch to the NumPy autocorrelation fallback, since losing time on installs is a common hackathon failure. Everyone should confirm that `import kivy, sounddevice, aubio` works in the first 15 minutes.

## 13. Six-Hour Build Plan

| Time | Deliverable | Owner |
| --- | --- | --- |
| 0:00-0:45 | Repo, virtual environment, Kivy window opens, mic stream works, live note shown | A (audio), C (UI) |
| 0:45-1:45 | Recording with count-in, notes segmented from frames | A |
| 1:45-2:45 | Key detection and quantization, melody playback through synth | A + B |
| **2:45** | **Checkpoint:** hum, then hear a cleaned melody in the right key. If not, use manual key selection and continue. | All |
| 2:45-3:45 | Chord generator and chord playback | B |
| 3:45-4:45 | Bass, two drum patterns, tempo slider, looping clock | B |
| 4:45-5:15 | Note strip, noise gate, UI polish | C |
| 5:15-6:00 | Testing with several voices, backup demo video, 60-second pitch | All |

Start B on hard-coded sample melodies from hour 1 so work is not blocked by the audio input.

## 14. Testing and Acceptance Criteria

### 14.1 Unit tests (pytest)

- Frequency to MIDI conversion is correct (440 Hz returns 69).
- A synthetic C major melody is detected as C major.
- A synthetic A minor melody is detected as A minor (or its relative key is accepted, if the notes are ambiguous).
- Notes outside the scale are snapped into the scale.
- Chord selection returns a chord containing the most melody notes for a given bar.

### 14.2 Manual acceptance tests

| Test | Pass condition |
| --- | --- |
| Hum a simple 4-bar tune | Key is correct or the relative key, and playback sounds in tune with the hum. |
| Silence | App shows "No notes detected" and does not crash. |
| Noisy room with headset mic | At least a usable melody is detected. |
| Change genre during playback | Drums change on the next loop with no crash or glitch. |
| Change tempo | Playback speed changes and stays steady. |
| Load demo melody | Full band plays without using the mic. |
| Run for 10 minutes looping | No timing drift or memory growth. |

## 15. Risks and Mitigations

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Audio library install problems | Medium | Test imports in the first 15 minutes. Keep NumPy fallback for pitch detection. |
| Playback timing drifts or crackles | Medium | Generate audio in blocks from one master clock inside the audio callback instead of using timers in the UI. |
| Pitch detection errors (octave jumps) | High | Median-filter pitch frames, fold octave jumps, and quantize generously. |
| Noisy demo room | High | Headset mic, noise gate, and the demo melody fallback. |
| Kivy UI freezing | Low | Keep all processing off the UI thread. |
| Android build fails | High | Treat Android as optional. Demo on desktop. |

## 16. Definition of Done

The project is done when a person can launch the app, press Record, hum four bars, and within a few seconds hear their melody played back in key with chords, bass and drums. The user can then change genre and tempo and replay, and the app handles silence and errors without crashing. A backup demo video and a one-minute pitch are ready.

## 17. Stretch Goals (only if the MVP is finished early)

- Per-track mute toggles and volume sliders.
- WAV export.
- Third genre (funk) and chord variation.
- A physical hardware knob (Arduino over serial) controlling tempo or genre, to strengthen a physical-computing angle.
- Android build with a native mic capture path.
