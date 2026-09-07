from panopilot.timeline_navigation import TimelineViewport, proportional_clip_widths


def test_timeline_zoom_keeps_anchor_near_same_fraction():
    view = TimelineViewport(120.0)
    view.zoom_steps(2, anchor_time=30.0)
    assert view.visible_duration < 120.0
    assert 0.0 <= view.visible_start < 30.0 < view.visible_end <= 120.0
    assert abs(view.fraction_for_time(30.0) - 0.25) < 1e-6


def test_timeline_pan_and_fit():
    view = TimelineViewport(120.0)
    view.zoom_steps(3, anchor_time=60.0)
    before = view.visible_start
    view.pan_fraction(0.5)
    assert view.visible_start > before
    view.fit()
    assert view.visible_start == 0.0
    assert view.visible_end == 120.0
    assert view.is_fitted


def test_ensure_visible_autoscrolls_long_timeline():
    view = TimelineViewport(120.0)
    view.set_window(0.0, 20.0)
    assert view.ensure_visible(19.5)
    assert view.visible_start > 0.0
    assert view.visible_start <= 19.5 <= view.visible_end


def test_scrollbar_state_tracks_visible_window():
    view = TimelineViewport(100.0)
    view.set_window(25.0, 20.0)
    state = view.scrollbar_state_ms()
    assert state["maximum"] == 80000
    assert state["page_step"] == 20000
    assert state["value"] == 25000


def test_clip_widths_are_proportional_to_trimmed_duration():
    widths = proportional_clip_widths([2.0, 4.0, 8.0], total_pixel_width=1400, minimum_width=40)
    assert widths[1] >= widths[0] * 1.9
    assert widths[2] >= widths[1] * 1.9


def test_range_thumbnail_helper_is_available_without_qt():
    from panopilot import thumbnails
    assert callable(thumbnails.sample_video_thumbnails_range)
