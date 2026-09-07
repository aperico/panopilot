from pathlib import Path

import panopilot.explore as explore


def _source():
    return Path(explore.__file__).read_text(encoding="utf-8")


def test_editor_has_explicit_back_to_project_action():
    source = _source()
    assert '"← Project" if embed_host is not None else "← Close"' in source
    assert "self.back_button.clicked.connect(self.close)" in source


def test_play_control_is_in_same_row_as_timeline():
    source = _source()
    assert "timeline_row.addWidget(self.play_button)" in source
    assert "timeline_row.addWidget(self.slider, 1)" in source
    assert source.index("timeline_row.addWidget(self.play_button)") < source.index("timeline_row.addWidget(self.slider, 1)")


def test_reframe_fine_controls_live_in_right_side_preview_rail():
    source = _source()
    assert 'self.reframe_frame.setMaximumWidth(230)' in source
    assert "preview_row.addWidget(self.canvas, 1)" in source
    assert "preview_row.addWidget(self.reframe_frame, 0)" in source
    assert "self.reframe_frame.setVisible(is_reframe)" in source


def test_camera_positions_render_as_diamonds_and_click_to_seek():
    source = _source()
    assert "def draw_diamond(marker_time, fill, outline):" in source
    assert "QPolygonF([" in source
    assert "painter.drawPolygon(polygon)" in source
    assert "widget._seek_to(original)" in source


def test_trim_hides_camera_rail_so_preview_gets_width_back():
    source = _source()
    assert "self.reframe_frame.setVisible(is_reframe)" in source
    assert "self.trim_frame.setVisible(not is_reframe)" in source


def test_thin_timeline_filmstrip_is_shared_by_reframe_and_trim():
    source = _source()
    assert "self._sync_timeline_view_controls()" in source
    assert "controls_layout.addWidget(self.timeline_thumbnail_frame)" in source
    assert "label.setFixedSize(tile_w, tile_h)" in source
    assert "label.setScaledContents(False)" in source
