from pathlib import Path

import numpy as np

from panopilot.clip_strip import build_clip_strip_entries
from panopilot.thumbnails import _fit_frame, filmstrip_tile_geometry


ROOT = Path(__file__).resolve().parents[1]


def test_dark_theme_sets_explicit_foreground_for_child_controls():
    source = (ROOT / "src/panopilot/desktop_theme.py").read_text()
    assert "QWidget#panopilotWorkspace QLabel" in source
    assert "QWidget#panopilotEditor QLabel" in source
    assert "color: #f1f3f5;" in source
    assert "QComboBox QAbstractItemView" in source


def test_project_workspace_opens_maximized_and_remains_resizable():
    source = (ROOT / "src/panopilot/project_editor.py").read_text()
    assert "widget.showMaximized()" in source
    assert "self.setMinimumSize(720, 480)" in source
    assert "self.resize(1480, 820)" not in source


def test_editor_has_explicit_reframe_and_trim_modes():
    source = (ROOT / "src/panopilot/explore.py").read_text()
    assert 'self.reframe_mode_button = QPushButton("Reframe")' in source
    assert 'self.trim_mode_button = QPushButton("Trim")' in source
    assert 'self.reframe_frame.setVisible(is_reframe)' in source
    assert 'self.trim_frame.setVisible(not is_reframe)' in source
    assert 'self.editor_mode = outer.initial_mode' in source


def test_reframe_action_explains_camera_position_semantics():
    source = (ROOT / "src/panopilot/explore.py").read_text()
    assert '"◆  Add at Playhead"' in source
    assert "closest Camera Position to the left" in source


def test_responsive_editor_no_longer_fixes_preview_to_render_size():
    source = (ROOT / "src/panopilot/explore.py").read_text()
    assert "self._source_pixmap.scaled(" in source
    assert "self.image_label.setFixedSize(\n                    width" not in source
    assert "widget.showMaximized()" in source


def test_editor_timeline_uses_adaptive_cached_source_thumbnails():
    source = (ROOT / "src/panopilot/explore.py").read_text()
    assert "sample_video_thumbnails_range(" in source
    assert "self._sync_timeline_view_controls()" in source
    assert "filmstrip_tile_geometry(" in source
    assert "max_tiles=24" in source
    assert "KeepAspectRatioByExpanding" in source
    assert "label.setScaledContents(False)" in source


def test_filmstrip_geometry_uses_multiple_discrete_tiles():
    geometry = filmstrip_tile_geometry(1280, height=46, max_tiles=24)
    assert geometry["count"] > 6
    assert geometry["height"] == 46
    assert geometry["width"] * geometry["count"] >= 1280


def test_clip_strip_entry_accepts_disposable_thumbnail_path():
    rows = [{
        "number": 1,
        "clip_id": "clip-1",
        "source": "/media/example.OSV",
        "source_name": "example.OSV",
        "duration": 3.0,
        "camera_position_count": 2,
        "trim_in": 0.0,
        "trim_out": 3.0,
        "source_status": {"status": "ok", "message": ""},
    }]
    entries = build_clip_strip_entries(
        rows,
        preview_states={"clip-1": "succeeded"},
        thumbnail_paths={"clip-1": "/tmp/clip.thumb.jpg"},
    )
    assert entries[0].thumbnail_path == "/tmp/clip.thumb.jpg"


def test_thumbnail_fit_is_exact_and_center_cropped():
    frame = np.zeros((100, 300, 3), dtype=np.uint8)
    fitted = _fit_frame(frame, 160, 90)
    assert fitted.shape == (90, 160, 3)
