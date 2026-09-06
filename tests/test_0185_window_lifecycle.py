from pathlib import Path

import panopilot.explore as explore_module
import panopilot.loading as loading_module
import panopilot.project_editor as project_editor_module


def _source(module):
    return Path(
        module.__file__
    ).read_text(
        encoding="utf-8"
    )


def test_loading_dialog_polls_worker_completion_on_gui_thread():
    source = _source(
        loading_module
    )

    assert "class PreparationThread(QThread)" in source
    assert "worker.isFinished()" in source
    assert "poll_timer.timeout.connect" in source
    assert "dialog.exec()" in source

    # The loading dialog must not rely on cross-thread loop.quit() signaling.
    assert "loop.quit()" not in source
    assert "QEventLoop" not in source


def test_project_editor_uses_local_qt_event_loop():
    source = _source(
        project_editor_module
    )

    assert "window_loop = QEventLoop()" in source
    assert "window_loop.exec()" in source
    assert "setQuitOnLastWindowClosed" in source
    assert "while widget.isVisible()" not in source


def test_clip_editor_uses_local_qt_event_loop():
    source = _source(
        explore_module
    )

    assert "window_loop = QEventLoop()" in source
    assert "window_loop.exec()" in source
    assert "setQuitOnLastWindowClosed" in source
    assert "while widget.isVisible()" not in source
