"""Editor rules (no Kivy, no audio). Geometry: 1000x418 widget, 64 px gutter, 18 px header."""
from core.editing import (EditSession, pitch_name, scale_degree, scale_pitches,
                          shift_diatonic)
from core.models import Note
from core.roll import RollGeometry

C_MAJOR = {0, 2, 4, 5, 7, 9, 11}


def make(notes, **kw):
    # plot = x 64..1064 (1000 px / 16 beats = 62.5 px per beat), rows lo=55..hi=79 -> 16 px each
    geo = RollGeometry(x=0, y=0, w=1064, h=418, gutter=64, header=18, total_beats=16, lo=55, hi=78)
    s = EditSession(geo, root=0, mode="major", grid=0.5, **kw)
    s.load(notes)
    return s


def bx(s, beat):
    return s.geo.beat_to_x(beat)


def cy(s, midi):
    return s.geo.pitch_to_y(midi) + s.geo.row_h / 2


def melody():
    return [Note(60, 0, 1), Note(62, 1, 1), Note(64, 2, 1), Note(65, 4, 2)]


def tuples(s):
    return [(n.midi, n.start, n.duration) for n in s.notes]


# ---------------------------------------------------------------- scale helpers
def test_scale_helpers_and_names():
    assert scale_degree(60, 0, "major") == 1 and scale_degree(61, 0, "major") is None
    assert scale_degree(69, 9, "minor") == 1
    assert shift_diatonic(60, 1, 0, "major") == 62 and shift_diatonic(64, 1, 0, "major") == 65
    assert shift_diatonic(60, 7, 0, "major") == 72 and shift_diatonic(60, -1, 0, "major") == 59
    assert shift_diatonic(61, 0, 0, "major") in (60, 62)          # out-of-scale gets snapped
    assert all(p % 12 in C_MAJOR for p in scale_pitches(0, "major"))
    assert pitch_name(60, 0, "major") == "C4" and pitch_name(70, 5, "major") == "Bb4"
    assert pitch_name(70, 0, "major") == "A#4"


# ------------------------------------------------------------- selection + hit
def test_click_select_shift_toggle_and_empty_click_clears():
    s = make(melody())
    s.press(bx(s, 0.5), cy(s, 60)); s.release()
    assert len(s.selected_notes()) == 1 and s.selected_notes()[0].midi == 60
    s.press(bx(s, 1.5), cy(s, 62), shift=True); s.release()
    assert sorted(n.midi for n in s.selected_notes()) == [60, 62]
    s.press(bx(s, 0.5), cy(s, 60), shift=True); s.release()        # shift-click toggles off
    assert [n.midi for n in s.selected_notes()] == [62]
    s.press(bx(s, 10), cy(s, 70)); s.release()                      # empty space
    assert not s.selected and not s.take_dirty()


def test_marquee_selects_group_and_shift_adds():
    s = make(melody())
    s.press(bx(s, -0.0) + 1, cy(s, 66) + 6)
    s.drag(bx(s, 3.5), cy(s, 59) - 6)
    assert s.marquee is not None
    s.release()
    assert sorted(n.midi for n in s.selected_notes()) == [60, 62, 64] and s.marquee is None
    s.press(bx(s, 4.0) + 3, cy(s, 70), shift=True)                   # box adds to selection
    s.drag(bx(s, 5.5), cy(s, 64))
    s.release()
    assert len(s.selected_notes()) == 4 and not s.take_dirty()


def test_click_inside_group_narrows_but_drag_keeps_group():
    s = make(melody()); s.select_all()
    s.press(bx(s, 0.5), cy(s, 60)); s.release()
    assert len(s.selected_notes()) == 1
    s.select_all()
    s.press(bx(s, 0.5), cy(s, 60)); s.drag(bx(s, 1.5), cy(s, 60)); s.release()
    assert len(s.selected_notes()) == 4


# ----------------------------------------------------------------- multi-edit
def test_group_move_in_time_keeps_intervals_and_snaps_to_grid():
    s = make(melody()); s.select_all()
    s.press(bx(s, 0.5), cy(s, 60))
    s.drag(bx(s, 0.5) + 70, cy(s, 60))             # +1.12 beats -> snaps to +1.0
    s.release()
    assert [n.start for n in s.notes] == [1, 2, 3, 5] and s.take_dirty()
    assert [n.midi for n in s.notes] == [60, 62, 64, 65]


def test_group_move_clamps_inside_the_loop():
    s = make(melody()); s.select_all()
    s.press(bx(s, 0.5), cy(s, 60)); s.drag(bx(s, 0.5) - 400, cy(s, 60)); s.release()
    assert s.notes[0].start == 0                      # can't go before beat 0
    s.select_all()
    s.press(bx(s, 0.5), cy(s, 60)); s.drag(bx(s, 0.5) + 900, cy(s, 60)); s.release()
    assert max(n.end for n in s.notes) == 16          # can't run past the loop end


def test_group_move_in_pitch_scale_lock_is_diatonic():
    s = make(melody(), scale_lock=True); s.select_all()
    s.press(bx(s, 0.5), cy(s, 60))
    s.drag(bx(s, 0.5), cy(s, 62))                     # grabbed C -> D = 1 scale step
    s.release()
    assert [n.midi for n in s.notes] == [62, 64, 65, 67]   # every note one step up in C major
    assert all(n.midi % 12 in C_MAJOR for n in s.notes) and s.take_dirty()


def test_group_move_in_pitch_scale_lock_off_is_chromatic():
    s = make(melody(), scale_lock=False); s.select_all()
    s.press(bx(s, 0.5), cy(s, 60)); s.drag(bx(s, 0.5), cy(s, 61)); s.release()
    assert [n.midi for n in s.notes] == [61, 63, 65, 66]


def test_group_move_stays_on_screen():
    s = make(melody(), scale_lock=False); s.select_all()
    s.press(bx(s, 0.5), cy(s, 60)); s.drag(bx(s, 0.5), cy(s, 60) + 800); s.release()
    assert max(n.midi for n in s.notes) <= s.geo.hi


def test_drag_unselected_note_moves_only_that_one():
    s = make(melody())
    s.press(bx(s, 4.5), cy(s, 65)); s.drag(bx(s, 5.5), cy(s, 65)); s.release()
    assert tuples(s)[-1] == (65, 5.0, 2) and tuples(s)[0] == (60, 0, 1)


def test_resize_group_from_right_edge_and_remembers_length():
    s = make(melody()); s.select_all()
    s.press(bx(s, 1.0) - 2, cy(s, 60))                # right edge of first note
    s.drag(bx(s, 1.0) - 2 + 63, cy(s, 60))            # +1 beat
    s.release()
    assert [n.duration for n in s.notes] == [2, 2, 2, 3] and s.take_dirty()
    assert s.default_len == 2
    s.select_all()
    s.press(bx(s, 1.0) - 2, cy(s, 60)); s.drag(bx(s, 0) , cy(s, 60)); s.release()
    assert min(n.duration for n in s.notes) >= s.grid   # never shorter than the grid


def test_drag_back_to_start_is_not_a_change():
    s = make(melody())
    s.press(bx(s, 0.5), cy(s, 60)); s.drag(bx(s, 3), cy(s, 60)); s.drag(bx(s, 0.5), cy(s, 60))
    s.release()
    assert not s.take_dirty() and tuples(s) == [(60, 0, 1), (62, 1, 1), (64, 2, 1), (65, 4, 2)]


# ---------------------------------------------------------------- add / delete
def test_double_click_adds_snapped_note_and_double_click_deletes():
    s = make(melody())
    s.press(bx(s, 8.3), cy(s, 61) , double=True); s.release()       # C# row -> snapped into key
    assert s.take_dirty() and len(s.notes) == 5
    added = s.selected_notes()[0]
    assert added.start == 8.0 and added.midi in (60, 62) and added.duration == 1.0
    s.press(bx(s, 8.5), cy(s, added.midi), double=True)
    assert len(s.notes) == 4 and s.take_dirty() and not s.selected


def test_add_note_ignores_exact_duplicate():
    s = make(melody())
    s.add_note(60, 0)
    assert len(s.notes) == 4 and not s.take_dirty()


def test_delete_selected_and_empty_melody_allowed():
    s = make(melody()); s.select_all()
    assert s.delete_selected() and s.notes == [] and s.take_dirty()
    assert not s.delete_selected()


# -------------------------------------------------------------------- commands
def test_transpose_steps_octaves_and_chromatic():
    s = make(melody()); s.select_all()
    assert s.transpose(steps=1) and [n.midi for n in s.notes] == [62, 64, 65, 67]
    assert s.transpose(octaves=-1) and [n.midi for n in s.notes] == [50, 52, 53, 55]
    assert s.geo.lo <= 49                                  # view grew to keep notes visible
    s2 = make(melody(), scale_lock=False); s2.select_all()
    assert s2.transpose(steps=1) and [n.midi for n in s2.notes] == [61, 63, 65, 66]


def test_nudge_clamps_and_nothing_selected_is_noop():
    s = make(melody())
    assert not s.nudge(0.5) and not s.transpose(steps=1)
    s.select_all()
    assert not s.nudge(-0.5)                               # already at beat 0
    assert s.nudge(1.0) and s.notes[0].start == 1
    assert s.nudge(100) and max(n.end for n in s.notes) == 16


def test_gutter_click_auditions_without_editing():
    heard = []
    s = make(melody()); s.on_preview = heard.append
    s.press(10, cy(s, 67)); s.release()
    assert heard == [67] and not s.take_dirty()


def test_load_keeps_selection_by_position_only_when_count_matches():
    s = make(melody()); s.selected = {id(s.notes[1])}
    s.load(s.result(), keep_selection=True)
    assert [n.midi for n in s.selected_notes()] == [62]
    s.load(s.result()[:3], keep_selection=True)
    assert not s.selected_notes()


def test_overlapping_duplicates_merge_after_move():
    s = make([Note(60, 0, 1), Note(60, 1, 2)])
    s.press(bx(s, 1.5), cy(s, 60)); s.drag(bx(s, 0.5), cy(s, 60)); s.release()
    assert tuples(s) == [(60, 0, 2)]


# ------------------------------------------------- scrolled-out notes (pitch pan)
def test_notes_scrolled_out_of_view_are_not_hit_or_box_selected():
    s = make(melody())
    s.geo.pan(12)                                    # view now ~67..90: every note is below it
    assert not any(s.in_view(n) for n in s.notes)
    s.press(bx(s, 0.5), cy(s, 72)); s.release()      # clicking where the notes would be drawn
    assert not s.selected
    s.press(bx(s, 0) + 1, s.geo.y + 2); s.drag(bx(s, 8), s.geo.plot_top - 2); s.release()
    assert not s.selected                            # box select ignores hidden notes
    s.select_all()
    assert len(s.selected) == 4                      # ...but Select all still means all


def test_transpose_grows_view_only_for_moved_notes():
    s = make(melody()); s.geo.pan(3)
    lo, hi = s.geo.lo, s.geo.hi
    s.selected = {id(s.notes[0])}                    # C4 (60) is in view
    s.transpose(steps=1)
    assert (s.geo.lo, s.geo.hi) == (lo, hi)
