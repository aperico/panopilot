from types import SimpleNamespace

import pytest

from test_056_home_workflow import home_window
from panopilot import project_editor


@pytest.mark.parametrize("enabled", [False, True])
def test_export_captures_extra_smoothing_choice(home_window, monkeypatch, tmp_path, enabled):
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    def confirm(box):
        assert not box.checkBox().isChecked()
        assert box.checkBox().isEnabled()
        box.checkBox().setChecked(enabled)
        return 0

    monkeypatch.setattr(QMessageBox, "exec", confirm)
    monkeypatch.setattr(QMessageBox, "clickedButton",
                        lambda box: next(b for b in box.buttons() if b.text() == "Export"))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(tmp_path / "out.mp4"), ""))
    captured = {}

    def export(*args, **kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(project_editor, "export_project_video", export)

    def check(w, app):
        tasks = []
        w._source_validation_failures = lambda: []
        w._save_before_child_window = lambda **kw: True
        w.background_jobs.submit = lambda key, title, task: tasks.append(task)
        w._export_project()
        assert len(tasks) == 1
        tasks[0](SimpleNamespace(check_cancelled=lambda: None, progress=lambda _: None, cancelled=False))
        assert captured["visual_stabilization"] is enabled
        assert captured["visual_stabilization_mode"] == "spherical"
        assert not list(tmp_path.glob(".*snapshot*"))
    home_window(1, check, stabilization_amount=.75)
