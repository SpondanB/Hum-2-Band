from core.models import Note
from core.roll import RollGeometry


def geo():
    return RollGeometry(x=10, y=20, w=1064, h=418, gutter=64, header=18, total_beats=16, lo=55, hi=78)


def test_mapping_round_trips():
    g = geo()
    for b in (0, 1.5, 8, 16):
        assert abs(g.x_to_beat(g.beat_to_x(b)) - b) < 1e-9
    for p in (55, 60, 78):
        assert g.y_to_pitch(g.pitch_to_y(p) + g.row_h / 2) == p
    assert g.y_to_pitch(-1000) == 55 and g.y_to_pitch(10 ** 6) == 78    # clamped
    assert abs(g.row_h * g.rows - g.plot_h) < 1e-9


def test_layout_regions():
    g = geo()
    assert g.plot_x == 74 and g.plot_top == 20 + 418 - 18
    assert g.beat_to_x(0) == g.plot_x and abs(g.beat_to_x(16) - g.plot_right) < 1e-9


def test_note_rect_has_minimum_width():
    g = geo()
    x0, y0, x1, y1 = g.note_rect(Note(60, 0, 0.001))
    assert x1 - x0 >= 3 and abs((y1 - y0) - g.row_h) < 1e-9


def test_fit_ensure_and_pan():
    g = geo()
    g.fit([Note(60, 0, 1), Note(67, 1, 1)])
    assert g.lo <= 57 and g.hi >= 70 and g.rows >= 16
    g.fit([])
    assert (g.lo, g.hi) == (48, 72)
    g.ensure_range([Note(30, 0, 1), Note(90, 0, 1)])
    assert g.lo <= 29 and g.hi >= 91
    g.pan(1000)
    assert g.hi == 108
    g.pan(-1000)
    assert g.lo == 21


def test_row_cap_keeps_rows_readable_and_panning_still_works():
    g = geo()
    assert g.rows_for_height(262, 13) == 20 and g.rows_for_height(10, 13) == 6   # floor
    g.fit([Note(40, 0, 1), Note(84, 1, 1)])                  # 3+ octaves of melody
    assert g.rows > 30
    assert g.set_max_rows(18) and g.rows == 18               # squeezed window -> capped
    assert g.row_h >= g.plot_h / 18 - 1e-9
    lo = g.lo
    g.pan(5)
    assert g.lo == lo + 5 and g.rows == 18                   # reach the rest by panning
    g.ensure_range([Note(30, 0, 1)])                         # edits still bring a note into view
    assert g.lo <= 30 <= g.hi and g.rows <= 18
    assert g.set_max_rows(None) is False                     # no cap -> unchanged
