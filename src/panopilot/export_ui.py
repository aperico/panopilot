"""Desktop export UX for PanoPilot.

0.38 separates the export *experience* from media rendering. The exporter emits
structured progress events and this module turns them into a stable overall
percentage, elapsed/remaining-time estimate, and completion/error dialogs.

The progress model is pure Python so behavior is testable without Qt.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import time

from .branding import set_application_icon


@dataclass(frozen=True)
class ExportProgressSnapshot:
    percent: float
    message: str
    phase: str
    elapsed_seconds: float
    remaining_seconds: float | None


def format_duration(seconds):
    if seconds is None or not math.isfinite(float(seconds)):
        return "—"

    value = max(0, int(round(float(seconds))))
    hours, remainder = divmod(value, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:d}:{secs:02d}"


def format_bytes(byte_count):
    value = max(0.0, float(byte_count))
    units = (
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
    )

    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0

    return f"{value:.1f} TB"


def build_export_summary(
    project,
    output_path,
    *,
    timeline_duration=None,
):
    """Return one stable user-facing summary of the saved export policy."""
    from .output_profile import (
        export_quality_for_project,
        output_profile_for_project,
    )

    output_path = Path(output_path)
    profile = output_profile_for_project(project)
    quality = export_quality_for_project(project)
    stabilization_percent = int(
        round(
            float(
                project.stabilization_amount
            )
            * 100.0
        )
    )

    lines = [
        f"File: {output_path.name}",
        f"Folder: {output_path.parent}",
        (
            "Video: "
            f"{profile.width}×{profile.height} "
            f"({profile.resolution}, {profile.aspect}) · "
            f"{profile.fps:.0f} fps"
            + (" (Auto)" if profile.fps_auto_selected else "")
        ),
        (
            "Quality: "
            f"{quality.label} · H.264 MP4"
        ),
        f"Clips: {len(project.clips)}",
        f"Stabilization: {stabilization_percent}%",
    ]

    if timeline_duration is not None:
        lines.insert(
            4,
            (
                "Duration: "
                f"{format_duration(timeline_duration)} "
                f"({float(timeline_duration):.1f} s)"
            ),
        )

    return {
        "text": "\n".join(lines),
        "profile": profile.to_dict(),
        "quality": quality.to_dict(),
        "stabilization_percent": stabilization_percent,
        "output": str(output_path),
        "timeline_duration": (
            float(timeline_duration)
            if timeline_duration is not None
            else None
        ),
    }


class ExportProgressModel:
    """Map detailed exporter events onto a monotonic 0..100 user progress.

    Rendering usually dominates export time. The weights therefore reserve the
    largest share for frame rendering while still making source inspection and
    rolling-shutter calibration visible instead of leaving an indeterminate
    spinner for minutes.
    """

    def __init__(
        self,
        *,
        expected_render_passes=1,
        started_at=None,
    ):
        self.expected_render_passes = max(
            1,
            int(expected_render_passes),
        )
        self.started_at = (
            time.monotonic()
            if started_at is None
            else float(started_at)
        )
        self.current_percent = 0.0
        self.render_pass = 1
        self.last_stage = "starting"

    def _render_range(self):
        if self.expected_render_passes <= 1:
            return 15.0, 90.0

        width = (
            75.0
            / self.expected_render_passes
        )
        start = 15.0 + width * (
            self.render_pass - 1
        )
        return start, start + width

    def _calibration_percent(self, event):
        clip_index = max(
            1,
            int(
                event.get(
                    "clip_index",
                    1,
                )
            ),
        )
        clip_count = max(
            clip_index,
            int(
                event.get(
                    "clip_count",
                    clip_index,
                )
            ),
        )
        candidate_index = max(
            0,
            int(
                event.get(
                    "candidate_index",
                    0,
                )
            ),
        )
        candidate_total = max(
            1,
            int(
                event.get(
                    "candidate_total",
                    1,
                )
            ),
        )
        clip_fraction = min(
            1.0,
            candidate_index
            / candidate_total,
        )
        overall_fraction = (
            (
                clip_index
                - 1
            )
            + clip_fraction
        ) / clip_count

        return 3.0 + 12.0 * overall_fraction

    def update(
        self,
        event,
        *,
        now=None,
    ):
        event = event or {}
        now = (
            time.monotonic()
            if now is None
            else float(now)
        )
        stage = str(
            event.get(
                "stage",
                "working",
            )
        )
        message = str(
            event.get(
                "message",
                "Exporting Project",
            )
        )
        candidate = self.current_percent

        if stage == "inspect":
            candidate = max(
                candidate,
                1.0,
            )

        elif stage in (
            "rolling-shutter-calibration",
            "rolling-shutter-calibration-progress",
        ):
            candidate = max(
                candidate,
                self._calibration_percent(
                    event
                ),
            )

        elif stage == "render-frame":
            pass_index = event.get(
                "render_pass_index"
            )
            if pass_index is not None:
                self.render_pass = max(
                    1,
                    min(
                        self.expected_render_passes,
                        int(pass_index),
                    ),
                )

            start, end = self._render_range()
            frame_percent = float(
                event.get(
                    "percent",
                    0.0,
                )
            )
            frame_fraction = max(
                0.0,
                min(
                    1.0,
                    frame_percent / 100.0,
                ),
            )
            candidate = start + (
                end - start
            ) * frame_fraction

        elif stage in (
            "visual-analysis",
            "spherical-visual-rerender",
        ):
            if self.expected_render_passes > 1:
                self.render_pass = min(
                    self.expected_render_passes,
                    max(
                        2,
                        self.render_pass + 1,
                    ),
                )
                start, _end = self._render_range()
                candidate = max(
                    candidate,
                    start,
                )
            else:
                candidate = max(
                    candidate,
                    86.0,
                )

        elif stage in (
            "visual-stabilization",
            "anchored-visual-stabilization",
            "extreme-visual-stabilization",
            "locked-visual-stabilization",
        ):
            event_percent = float(
                event.get(
                    "percent",
                    50.0,
                )
            )
            candidate = max(
                candidate,
                70.0
                + 0.20
                * max(
                    0.0,
                    min(
                        100.0,
                        event_percent,
                    ),
                ),
            )

        elif stage == "audio":
            candidate = max(
                candidate,
                92.0,
            )

        elif stage == "mux":
            candidate = max(
                candidate,
                96.0,
            )

        elif stage == "verify":
            candidate = max(
                candidate,
                98.5,
            )

        elif stage == "completed":
            candidate = 100.0

        # UX invariant: progress never runs backwards.
        self.current_percent = max(
            self.current_percent,
            min(
                100.0,
                float(candidate),
            ),
        )
        self.last_stage = stage
        elapsed = max(
            0.0,
            now - self.started_at,
        )
        remaining = None

        if (
            2.0
            <= self.current_percent
            < 99.9
            and elapsed >= 3.0
        ):
            remaining = (
                elapsed
                * (
                    100.0
                    - self.current_percent
                )
                / self.current_percent
            )

        return ExportProgressSnapshot(
            percent=float(
                self.current_percent
            ),
            message=message,
            phase=stage,
            elapsed_seconds=float(elapsed),
            remaining_seconds=(
                float(remaining)
                if remaining is not None
                and math.isfinite(remaining)
                else None
            ),
        )


def run_export_with_progress_dialog(
    task,
    *,
    output,
    expected_render_passes=1,
):
    """Run ``task(progress_event)`` with a determinate export dialog."""
    try:
        from queue import (
            Empty,
            SimpleQueue,
        )
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
            "PySide6 is required for the PanoPilot export dialog."
        ) from exc

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
        app.setApplicationName(
            "PanoPilot"
        )

    set_application_icon(app)
    output = Path(output)
    dialog = QDialog()
    dialog.setWindowTitle(
        "PanoPilot — Exporting"
    )
    dialog.setWindowModality(
        Qt.WindowModality.ApplicationModal
    )
    dialog.setModal(True)
    dialog.setMinimumWidth(520)
    dialog.setWindowFlag(
        Qt.WindowType.WindowCloseButtonHint,
        False,
    )

    title_label = QLabel(
        "Exporting Project"
    )
    title_label.setStyleSheet(
        "font-size: 17px; font-weight: 600;"
    )
    file_label = QLabel(
        output.name
    )
    file_label.setStyleSheet(
        "color: palette(mid);"
    )
    progress_bar = QProgressBar()
    progress_bar.setRange(
        0,
        1000,
    )
    progress_bar.setValue(
        0
    )
    progress_bar.setFormat(
        "%p%"
    )
    status_label = QLabel(
        "Starting…"
    )
    status_label.setWordWrap(
        True
    )
    timing_label = QLabel(
        "Elapsed 0:00 · Remaining —"
    )
    timing_label.setStyleSheet(
        "color: palette(mid);"
    )

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(
        22,
        20,
        22,
        20,
    )
    layout.setSpacing(
        10
    )
    layout.addWidget(
        title_label
    )
    layout.addWidget(
        file_label
    )
    layout.addWidget(
        progress_bar
    )
    layout.addWidget(
        status_label
    )
    layout.addWidget(
        timing_label
    )

    progress_queue = SimpleQueue()
    model = ExportProgressModel(
        expected_render_passes=(
            expected_render_passes
        )
    )

    class ExportThread(QThread):
        def __init__(self):
            super().__init__()
            self.value = None
            self.error = None

        def report_progress(
            self,
            event,
        ):
            if isinstance(
                event,
                dict,
            ):
                progress_queue.put(
                    dict(event)
                )
            else:
                progress_queue.put(
                    {
                        "stage": "working",
                        "message": str(event),
                    }
                )

        def run(self):
            try:
                self.value = task(
                    self.report_progress
                )
            except BaseException as exc:
                self.error = exc

    worker = ExportThread()
    timer = QTimer(dialog)
    timer.setInterval(
        100
    )

    def poll():
        latest = None
        while True:
            try:
                latest = progress_queue.get_nowait()
            except Empty:
                break

        if latest is not None:
            snapshot = model.update(
                latest
            )
            progress_bar.setValue(
                int(
                    round(
                        snapshot.percent
                        * 10.0
                    )
                )
            )
            status_label.setText(
                snapshot.message
            )
            timing_label.setText(
                "Elapsed "
                + format_duration(
                    snapshot.elapsed_seconds
                )
                + " · Remaining "
                + (
                    "~"
                    + format_duration(
                        snapshot.remaining_seconds
                    )
                    if snapshot.remaining_seconds
                    is not None
                    else "—"
                )
            )
        else:
            elapsed = (
                time.monotonic()
                - model.started_at
            )
            timing_label.setText(
                "Elapsed "
                + format_duration(
                    elapsed
                )
                + " · Remaining "
                + (
                    "~"
                    + format_duration(
                        elapsed
                        * (
                            100.0
                            - model.current_percent
                        )
                        / model.current_percent
                    )
                    if model.current_percent
                    >= 2.0
                    and elapsed >= 3.0
                    else "—"
                )
            )

        if worker.isFinished():
            timer.stop()
            progress_bar.setValue(
                1000
            )
            dialog.accept()

    timer.timeout.connect(
        poll
    )
    worker.start()
    timer.start()
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    dialog.exec()
    worker.wait()
    poll()

    error = worker.error
    value = worker.value
    timer.deleteLater()
    worker.deleteLater()
    dialog.deleteLater()
    app.processEvents()

    if error is not None:
        raise error

    return value


def show_export_completion_dialog(
    result,
):
    """Show final file facts and provide an Open Folder action."""
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import (
            QApplication,
            QMessageBox,
        )
    except ImportError as exc:
        raise RuntimeError(
            "PySide6 is required for the PanoPilot export completion dialog."
        ) from exc

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
        app.setApplicationName(
            "PanoPilot"
        )

    set_application_icon(app)
    output = Path(
        result["output"]
    )
    profile = result.get(
        "output_profile",
        {},
    )
    encoder = result.get(
        "encoder",
        {},
    )
    quality = (
        encoder.get(
            "quality",
            {},
        ).get(
            "label",
            "H.264",
        )
    )
    file_size = (
        int(
            result.get(
                "output_file_size_bytes"
            )
        )
        if result.get(
            "output_file_size_bytes"
        ) is not None
        else (
            output.stat().st_size
            if output.is_file()
            else 0
        )
    )
    processing = (
        result.get(
            "performance",
            {},
        ).get(
            "processing_seconds"
        )
    )

    dialog = QMessageBox()
    dialog.setWindowTitle(
        "PanoPilot — Export complete"
    )
    dialog.setIcon(
        QMessageBox.Icon.Information
    )
    dialog.setText(
        "Project export complete"
    )
    dialog.setInformativeText(
        "\n".join(
            [
                f"{output.name}",
                (
                    f"{profile.get('width', '?')}×"
                    f"{profile.get('height', '?')} · "
                    f"{profile.get('fps', 30):.0f} fps · "
                    f"{quality}"
                ),
                f"Duration: {format_duration(result.get('encoded_duration'))}",
                f"File size: {format_bytes(file_size)}",
                (
                    "Export time: "
                    + format_duration(
                        processing
                    )
                    if processing is not None
                    else ""
                ),
                "",
                str(output),
            ]
        ).strip()
    )
    open_folder = dialog.addButton(
        "Open Folder",
        QMessageBox.ButtonRole.ActionRole,
    )
    dialog.addButton(
        "Close",
        QMessageBox.ButtonRole.AcceptRole,
    )
    dialog.exec()

    if dialog.clickedButton() is open_folder:
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(
                str(
                    output.parent.resolve()
                )
            )
        )

    dialog.deleteLater()
    app.processEvents()


def show_export_error_dialog(
    error,
    *,
    output=None,
):
    try:
        from PySide6.QtWidgets import (
            QApplication,
            QMessageBox,
        )
    except ImportError:
        return

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
        app.setApplicationName(
            "PanoPilot"
        )

    set_application_icon(app)
    detail = str(error)
    if output:
        detail += (
            "\n\nDestination:\n"
            + str(output)
        )

    QMessageBox.critical(
        None,
        "PanoPilot — Export failed",
        detail,
    )
