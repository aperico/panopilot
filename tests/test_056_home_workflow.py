"""Exercise real Qt controls without decoding media or opening native dialogs."""
import json
from types import SimpleNamespace

import pytest

from panopilot import project_editor
from panopilot.project import Project


@pytest.fixture
def home_window(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QEventLoop
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(project_editor, "source_duration", lambda _: 5.0)
    monkeypatch.setattr(project_editor.BackgroundJobManager, "submit", lambda *a, **kw: None)

    def run(clip_count, check, *, stabilization_amount=0.0):
        project = Project(stabilization_amount=stabilization_amount)
        for index in range(clip_count):
            source = tmp_path / f"clip-{index}.OSV"
            source.write_bytes(b"test source; decoding is stubbed")
            project.add_clip(str(source), source_identity_value=None)
        path = tmp_path / "project.json"
        path.write_text(json.dumps(project.to_dict()))

        def inspect(_loop):
            window = next(w for w in app.topLevelWidgets()
                          if w.objectName() == "panopilotWorkspace" and w.isVisible())
            window.showNormal()
            window.resize(720, 480)
            app.processEvents()
            try:
                check(window, app)
            finally:
                window.close()
                window.deleteLater()
                app.processEvents()
            return 0

        monkeypatch.setattr(QEventLoop, "exec", inspect)
        project_editor.run_project_editor(path)
    return run


def test_empty_home_has_one_clear_start_and_no_unusable_workflow(home_window):
    def check(w, app):
        assert w.home_start_button.isVisible() and w.home_start_button.isEnabled()
        assert not w.home_workflow.isVisible()
        assert not w.clip_strip_frame.isVisible()
        assert w.home_settings_button.isVisible()
        assert not w.export_action.isEnabled()
        assert not w.edit_action.isEnabled()
        assert "Add clips" in w.home_hint.text()
    home_window(0, check)


def test_selection_updates_edit_routing_and_reorder_boundaries(home_window):
    def check(w, app):
        assert not w.home_start_button.isVisible()
        assert w.home_workflow.isVisible()
        assert w.home_preview_button.isEnabled() and w.home_export_button.isEnabled()
        assert not w.move_earlier_action.isEnabled()
        assert w.move_later_action.isEnabled()
        w.list.clearSelection()
        assert not w.home_edit_button.isEnabled()
        assert not w.edit_action.isEnabled()
        assert "Choose a clip" in w.home_heading.text()
        second_id = w.clip_model.clip_id_for_index(w.clip_model.index(1, 0))
        w._select_clip_id(second_id)
        assert w.home_edit_button.isEnabled()
        assert w.move_earlier_action.isEnabled()
        assert not w.move_later_action.isEnabled()
        assert "clip-1.OSV" in w.home_heading.text()
        calls = []
        w._edit_selected = lambda: calls.append(w._selected_clip_id())
        w.home_edit_button.click()
        assert calls == [second_id]
        w._show_arrange_mode()
        assert w.workspace_mode == "arrange"
        assert not w.clip_strip_frame.isVisible()
        w.arrange_widget.back_button.click()
        assert w.workspace_mode == "home"
        assert w._selected_clip_id() == second_id
        assert w.home_edit_button.isEnabled()
    home_window(2, check)


def test_preparing_and_failed_previews_explain_next_action(home_window):
    def check(w, app):
        for state, message in [("running", "when ready"), ("failed", "retry")]:
            w._preview_snapshot = lambda _, state=state: SimpleNamespace(state=state)
            w._update_home_guidance()
            assert message in w.home_hint.text()
            assert w.home_edit_button.isEnabled()
    home_window(1, check)


def test_unavailable_recording_explains_recovery_and_disables_edit(home_window):
    def check(w, app):
        from pathlib import Path
        entry = w.clip_model.entry(w.list.currentIndex())
        source = Path(entry.source)
        source.unlink()
        w._update_clip_menu_visibility()
        assert "Recording unavailable" in w.home_hint.text()
        assert not w.edit_action.isEnabled() and not w.home_edit_button.isEnabled()
        assert w.remove_action.isEnabled()
        source.write_bytes(b"test source; decoding is stubbed")
        w._update_clip_menu_visibility()
        assert w.home_edit_button.isEnabled()
    home_window(1, check)


@pytest.mark.parametrize("clip_count", [0, 2])
def test_home_controls_fit_minimum_window_size(home_window, clip_count):
    def check(w, app):
        from PySide6.QtCore import QPoint, QRect
        assert w.width() == 720 and w.height() == 480
        # Layouts must not squash controls on top of one another. Small windows
        # may scroll the Home panel; keyboard focus must still reach every action.
        labels = [w.home_name_edit, w.home_summary_label, w.home_heading, w.home_hint]
        for first, second in zip(labels, labels[1:]):
            assert not first.geometry().intersects(second.geometry())
        for button in (w.home_start_button, w.home_edit_button, w.home_arrange_button,
                       w.home_preview_button, w.home_export_button, w.home_settings_button):
            if button.isVisible():
                w.home_scroll.ensureWidgetVisible(button)
                app.processEvents()
                viewport = w.home_scroll.viewport()
                bounds = QRect(button.mapTo(viewport, QPoint(0, 0)), button.size())
                assert viewport.rect().contains(bounds), (button.text(), bounds, viewport.size())
                assert button.height() >= button.minimumSizeHint().height()
    home_window(clip_count, check)
