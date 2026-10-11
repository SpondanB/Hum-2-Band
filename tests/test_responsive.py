from ui.responsive import MAX_SCALE, MIN_SCALE, compute_layout


def test_design_size_is_scale_one_and_wide():
    lay = compute_layout(1000, 680)
    assert lay.scale == 1.0 and lay.wide and not lay.compact


def test_small_laptop_window_stays_wide_and_readable():
    lay = compute_layout(1280, 700)                 # 1366x768 laptop minus chrome
    assert lay.wide and 1.0 <= lay.scale <= 1.1


def test_4k_and_tablet_scale_up_but_are_capped():
    assert compute_layout(3840, 2160).scale == MAX_SCALE
    assert 1.2 <= compute_layout(1280, 800).scale <= 1.3


def test_tiny_windows_never_shrink_below_the_floor():
    assert compute_layout(300, 200).scale == MIN_SCALE


def test_portrait_phone_stacks_and_is_compact():
    lay = compute_layout(400, 800)
    assert not lay.wide and lay.compact


def test_landscape_phone_uses_side_panel():
    lay = compute_layout(800, 360)
    assert lay.wide and not lay.compact


def test_square_ish_window_stacks():
    assert not compute_layout(900, 900).wide        # no room for a side panel next to the roll


def test_scale_is_quantised_to_avoid_churn():
    scales = {compute_layout(w, 680).scale for w in range(1000, 1011)}
    assert len(scales) == 1


def test_degenerate_sizes_do_not_crash():
    for w, h in ((0, 0), (1, 1), (-5, 100)):
        assert compute_layout(w, h).scale == MIN_SCALE
