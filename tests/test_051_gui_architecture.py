from pathlib import Path
import panopilot.explore as explore
import panopilot.project_editor as project_editor


def _source(module):
    return Path(module.__file__).read_text(encoding="utf-8")


def test_clip_timeline_has_zoom_pan_fit_and_horizontal_scroll_controls():
    source = _source(explore)
    assert "self.timeline_view = TimelineViewport(" in source
    assert "self.timeline_scroll = QScrollBar(Qt.Orientation.Horizontal)" in source
    assert "self.timeline_zoom_out = QPushButton(\"−\")" in source
    assert "self.timeline_fit = QPushButton(\"Fit\")" in source
    assert "self.timeline_zoom_in = QPushButton(\"+\")" in source
    assert "owner._handle_timeline_wheel" in source
    assert "self.timeline_view.ensure_visible" in source


def test_timeline_thumbnails_are_resampled_for_visible_zoom_window():
    source = _source(explore)
    assert "sample_video_thumbnails_range(" in source
    assert "start_time=self.timeline_view.visible_start" in source
    assert "end_time=self.timeline_view.visible_end" in source
    assert "count=key[2]" in source


def test_clip_editor_exposes_only_reframe_and_trim_modes():
    source = _source(explore)
    assert 'self.reframe_mode_button = QPushButton("Reframe")' in source
    assert 'self.trim_mode_button = QPushButton("Trim")' in source
    assert 'self.arrange_mode_button = QPushButton("Arrange")' not in source
    assert "mode_row.addWidget(self.arrange_mode_button)" not in source


def test_project_home_edits_name_and_exposes_edit_and_project_settings():
    source = _source(project_editor)
    assert 'self.home_name_edit = QLineEdit()' in source
    assert 'self.home_name_edit.setObjectName("projectNameEdit")' in source
    assert 'self.home_settings_button = QPushButton("Project Settings…")' in source
    assert 'self.home_edit_button = QPushButton("Edit Selected Clip")' in source
    assert 'self.home_arrange_button = QPushButton("Arrange Clips")' in source
    assert 'self.home_export_button = QPushButton("Export Final Video…")' in source
    assert 'self.home_open_button = QPushButton("Open Project…")' in source
    assert "self.home_name_edit.editingFinished.connect" in source


def test_file_menu_has_save_as_for_multiple_project_files():
    source = _source(project_editor)
    assert 'self.save_as_action = QAction("Save Project &As…", self)' in source
    assert "file_menu.addAction(self.save_as_action)" in source
    assert "session.save(target_path)" in source
    assert "project_path = target_path" in source


def test_arrange_uses_duration_proportional_cards_drag_drop_and_same_timeline_model():
    source = _source(project_editor)
    assert "class ArrangeTimelineWidget(QWidget):" in source
    assert "self.timeline_view = TimelineViewport(0.0)" in source
    assert "proportional_clip_widths(" in source
    assert "drag.exec(Qt.DropAction.MoveAction)" in source
    assert "self.reorder_callback(source_id, target_index)" in source
    assert "def handle_wheel(self, event):" in source
