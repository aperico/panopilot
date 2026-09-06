"""
Foreground loading UI for PanoPilot media preparation.

The preparation task runs on a QThread. The modal QDialog owns the nested Qt
event loop, while a GUI-thread QTimer polls worker completion and progress.

This deliberately avoids cross-thread "quit the event loop" signaling. A cached
preview may finish before the dialog event loop begins; the first timer tick
simply observes the already-finished worker and closes the dialog normally.
"""
from __future__ import annotations

from queue import Empty, SimpleQueue


def run_with_loading_screen(
    task,
    *,
    title="PanoPilot",
    message="Preparing…",
    detail=None,
):
    """
    Run ``task(progress)`` while a responsive modal loading dialog is visible.

    ``progress(text)`` may be called from the worker. The function returns the
    task result and re-raises task exceptions on the GUI/caller thread.
    """
    try:
        from PySide6.QtCore import (
            QThread,
            QTimer,
            Qt,
        )
        from PySide6.QtWidgets import (
            QApplication,
            QDialog,
            QLabel,
            QProgressBar,
            QVBoxLayout,
        )
    except ImportError as exc:
        raise RuntimeError(
            "PySide6 is required for the PanoPilot loading screen."
        ) from exc

    app = QApplication.instance()

    if app is None:
        app = QApplication([])
        app.setApplicationName("PanoPilot")

    dialog = QDialog()
    dialog.setWindowTitle(str(title))
    dialog.setWindowModality(
        Qt.WindowModality.ApplicationModal
    )
    dialog.setModal(True)
    dialog.setMinimumWidth(440)

    # Preview preparation is not cancellation-safe yet.
    dialog.setWindowFlag(
        Qt.WindowType.WindowCloseButtonHint,
        False,
    )

    title_label = QLabel(str(message))
    title_label.setStyleSheet(
        "font-size: 16px; font-weight: 600;"
    )

    detail_label = QLabel(
        str(detail or "")
    )
    detail_label.setWordWrap(True)
    detail_label.setStyleSheet(
        "color: palette(mid);"
    )

    progress_bar = QProgressBar()
    progress_bar.setRange(0, 0)
    progress_bar.setTextVisible(False)

    status_label = QLabel("Starting…")
    status_label.setWordWrap(True)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(
        22,
        20,
        22,
        20,
    )
    layout.setSpacing(10)
    layout.addWidget(title_label)

    if detail:
        layout.addWidget(detail_label)

    layout.addWidget(progress_bar)
    layout.addWidget(status_label)

    progress_queue = SimpleQueue()

    class PreparationThread(QThread):
        def __init__(self):
            super().__init__()
            self.value = None
            self.error = None

        def report_progress(self, text):
            progress_queue.put(
                str(text)
            )

        def run(self):
            try:
                self.value = task(
                    self.report_progress
                )
            except BaseException as exc:
                self.error = exc

    worker = PreparationThread()

    poll_timer = QTimer(dialog)
    poll_timer.setInterval(50)

    def poll_worker():
        # Drain any progress generated since the previous GUI tick.
        latest = None

        while True:
            try:
                latest = progress_queue.get_nowait()
            except Empty:
                break

        if latest is not None:
            status_label.setText(
                str(latest)
            )

        # This is the single completion boundary. It runs on the GUI thread.
        if worker.isFinished():
            poll_timer.stop()
            dialog.accept()

    poll_timer.timeout.connect(
        poll_worker
    )

    # Start both before exec(). If the worker finishes immediately, that is
    # harmless: the first timer event in dialog.exec() observes isFinished()
    # and accepts the dialog.
    worker.start()
    poll_timer.start()

    dialog.show()
    dialog.raise_()
    dialog.activateWindow()

    dialog.exec()

    # The dialog can only accept automatically after isFinished(), but wait()
    # also makes the ownership boundary explicit before returning task data.
    worker.wait()

    # One final progress drain is useful for diagnostics/status consistency.
    poll_worker()

    error = worker.error
    value = worker.value

    poll_timer.deleteLater()
    worker.deleteLater()
    dialog.deleteLater()
    app.processEvents()

    if error is not None:
        raise error

    return value
