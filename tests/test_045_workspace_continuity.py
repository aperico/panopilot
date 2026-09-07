from pathlib import Path

import panopilot.project_editor as project_editor


def test_project_workspace_is_focus_first_and_keeps_sequence_accessible():
    source = Path(project_editor.__file__).read_text(encoding="utf-8")

    assert "focus-first workspace" in source
    assert "create_qt_clip_strip_model" in source
    assert "self.clip_strip_frame" in source
    assert "QListView.ViewMode.IconMode" in source
    assert "self.workspace_splitter" not in source
    assert "embed_host=self.editor_host" in source
    assert "on_closed=lambda result" in source
    assert "load_project(project_path)" in source
    assert "self._clip_editor_closed" in source


def test_project_workspace_exposes_fps_control_behind_project_settings():
    source = Path(project_editor.__file__).read_text(encoding="utf-8")

    for token in (
        "self.settings_action",
        "self.settings_dialog = QDialog(self)",
        'settings_menu = self.menuBar().addMenu("&Settings")',
        "self.fps_combo",
        "Auto (60 fps recommended)",
        "24 fps",
        "25 fps",
        "30 fps",
        "50 fps",
        "60 fps",
        "_fps_changed",
    ):
        assert token in source


def test_explore_editor_supports_nonblocking_embedded_workspace_mode():
    import panopilot.explore as explore

    source = Path(explore.__file__).read_text(encoding="utf-8")
    assert "def run(self, *, embed_host=None, on_closed=None):" in source
    assert "if on_closed is not None:" in source
    assert 'return {"embedded": True}' in source
    assert "on_closed(final_state)" in source
    assert "embedded_layout.addWidget(widget)" in source


def test_explore_editor_keeps_fine_controls_visible_in_reframe():
    import panopilot.explore as explore

    source = Path(explore.__file__).read_text(encoding="utf-8")
    assert 'self.advanced_frame = QFrame()' in source
    assert 'reframe_layout.addWidget(self.advanced_frame, 1)' in source
    assert 'self.advanced_frame.setVisible(is_reframe)' in source
    assert 'self.advanced_button' not in source
