from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_EDITOR = (ROOT / "src" / "panopilot" / "project_editor.py").read_text(encoding="utf-8")


def test_clip_menu_hides_selection_only_actions_without_selected_clip():
    assert "def _update_clip_menu_visibility(self):" in PROJECT_EDITOR
    assert "selection_model.selectedIndexes()" in PROJECT_EDITOR
    assert "action.setVisible(selection_actions_visible)" in PROJECT_EDITOR
    assert "self.clip_selection_separator.setVisible(selection_actions_visible)" in PROJECT_EDITOR
    assert "self.arrange_action" not in PROJECT_EDITOR[
        PROJECT_EDITOR.index("def _update_clip_menu_visibility(self):"):
        PROJECT_EDITOR.index("def _edit_clip_index", PROJECT_EDITOR.index("def _update_clip_menu_visibility(self):"))
    ]


def test_clip_menu_visibility_reacts_to_browser_selection_changes():
    assert "self.list.selectionModel().selectionChanged.connect(" in PROJECT_EDITOR
    assert "lambda *_args: self._update_clip_menu_visibility()" in PROJECT_EDITOR
    assert "self._update_clip_menu_visibility()" in PROJECT_EDITOR


def test_export_controls_get_reserved_status_bar_space_and_abort_label():
    assert 'self.abort_export_button = QPushButton("Abort")' in PROJECT_EDITOR
    assert "self.abort_export_button.setFixedWidth(64)" in PROJECT_EDITOR
    assert "self.export_progress.setFixedWidth(104)" in PROJECT_EDITOR
    assert "status_bar.addWidget(self.project_info, 2)" in PROJECT_EDITOR
    assert "status_bar.addPermanentWidget(self.export_progress)" in PROJECT_EDITOR
    assert "status_bar.addPermanentWidget(self.abort_export_button)" in PROJECT_EDITOR
    assert "status_bar.setSizeGripEnabled(False)" in PROJECT_EDITOR
    assert 'QPushButton("Cancel")' not in PROJECT_EDITOR


def test_background_status_uses_compact_labels_with_tooltips_for_detail():
    for label in (
        'self.work_status = QLabel("Idle")',
        'self.work_status.setText("Exporting…")',
        'self.work_status.setText("Validating media…")',
        'self.work_status.setText("Preparing Clip…")',
    ):
        assert label in PROJECT_EDITOR
    assert "self.work_status.setToolTip(" in PROJECT_EDITOR
