"""Screen-size -> layout decisions. Pure Python (no Kivy), so it is unit-tested.

Sizes are in dp. Two independent decisions:

* scale   - one multiplier for control heights / fonts / the piano roll's gutter, so the
            app is as comfortable on a 4K monitor or tablet as on a laptop.
* wide    - True  => piano roll on the left, settings in a scrolling panel on the right
            False => piano roll on top, settings in a scrolling panel underneath
            In both modes the piano roll and the transport (Record / Play) stay pinned;
            only the secondary settings scroll.
* compact - narrow window: fewer columns, chord names move to their own line.
"""
from dataclasses import dataclass

BASE_W, BASE_H = 1000.0, 680.0         # the size the design was drawn for (scale = 1.0)
MIN_SCALE, MAX_SCALE = 0.85, 1.6
WIDE_MIN_W = 860.0                     # side-by-side needs room for roll + 340dp panel
COMPACT_MAX_W = 600.0


@dataclass(frozen=True)
class Layout:
    scale: float
    wide: bool
    compact: bool


def compute_layout(width_dp, height_dp):
    w, h = max(1.0, float(width_dp)), max(1.0, float(height_dp))
    scale = min(w / BASE_W, h / BASE_H)
    scale = max(MIN_SCALE, min(MAX_SCALE, scale))
    scale = round(scale * 20) / 20                 # 0.05 steps: no relayout churn while dragging
    landscape_desktop = w >= WIDE_MIN_W and w >= 1.05 * h
    landscape_phone = w >= 560 and w >= 1.6 * h    # short + wide: side panel beats stacking
    return Layout(scale=scale, wide=landscape_desktop or landscape_phone,
                  compact=w < COMPACT_MAX_W)
