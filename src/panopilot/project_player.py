"""
Sequential PanoPilot Project Timeline preview.

The Project Player is intentionally read-only. It consumes:

    Project Time
        ↓
    active Clip instance
        ↓
    Source Time
        ↓
    cached panoramic preview
        +
    persisted View Path / Camera Motion
        ↓
    conventional preview frame

At Clip boundaries it switches both the panoramic preview source and the
corresponding source audio.

This is the Iteration-1 preview path, not final-quality export. Cached panoramic
media is derived and disposable; authoritative edit state remains in the
Project and authoritative media remains the original OSV.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import time

import cv2

from .cache import (
    PanoramaCacheReader,
    PreviewProfile,
    ensure_preview_cache,
)
from .loading import run_with_loading_screen
from .project import Project, load_project
from .timeline import (
    ClipTimelineSpan,
    build_project_timeline,
    timeline_time_to_source,
)
from .virtual_camera import (
    aspect_dimensions,
    reframe_equirectangular,
)
from .view_path import evaluate_clip_view_path


WINDOW_TITLE = "PanoPilot — Project Preview"


@dataclass(frozen=True)
class ProjectPlaybackState:
    project_time: float
    project_duration: float
    clip_index: int
    clip_id: str
    source: str
    source_time: float
    clip_time: float
    camera_mode: str
    camera_yaw_deg: float
    camera_pitch_deg: float
    camera_fov_deg: float

    def to_dict(self):
        return {
            "project_time": float(
                self.project_time
            ),
            "project_duration": float(
                self.project_duration
            ),
            "clip_index": int(
                self.clip_index
            ),
            "clip_id": self.clip_id,
            "source": self.source,
            "source_time": float(
                self.source_time
            ),
            "clip_time": float(
                self.clip_time
            ),
            "camera_mode": self.camera_mode,
            "camera": {
                "yaw_deg": float(
                    self.camera_yaw_deg
                ),
                "pitch_deg": float(
                    self.camera_pitch_deg
                ),
                "fov_deg": float(
                    self.camera_fov_deg
                ),
            },
        }


def project_playback_start_time(
    project_time,
    project_duration,
    *,
    tolerance_s=0.001,
):
    """
    Resolve Play behavior.

    If the playhead is at the end of the Project Timeline, Play restarts from
    Project Time 0. Otherwise playback resumes from the current Project Time.
    """
    project_duration = max(
        0.0,
        float(project_duration),
    )
    project_time = max(
        0.0,
        min(
            float(project_time),
            project_duration,
        ),
    )
    tolerance_s = max(
        0.0,
        float(tolerance_s),
    )

    if (
        project_duration > 0.0
        and project_time
        >= project_duration - tolerance_s
    ):
        return 0.0

    return project_time


def project_state_at(
    project: Project,
    spans,
    project_time,
):
    """
    Evaluate one Project Timeline position without decoding media.
    """
    spans = list(spans)

    if not spans:
        raise ValueError(
            "Cannot evaluate an empty Project Timeline"
        )

    total_duration = float(
        spans[-1].timeline_end
    )

    span, source_time = (
        timeline_time_to_source(
            spans,
            project_time,
        )
    )

    clip = project.clip_for_id(
        span.clip_id
    )

    if clip is None:
        raise RuntimeError(
            f"Timeline references missing Clip {span.clip_id}"
        )

    clip_index = project.clip_index(
        clip.id
    )

    if clip_index is None:
        raise RuntimeError(
            f"Clip {clip.id} is not present in Project order"
        )

    sample = evaluate_clip_view_path(
        clip,
        source_time,
        interpolation=(
            project.camera_motion_easing
        ),
        strength=(
            project.camera_motion_strength
        ),
    )

    return ProjectPlaybackState(
        project_time=float(
            project_time
        ),
        project_duration=total_duration,
        clip_index=int(
            clip_index
        ),
        clip_id=clip.id,
        source=clip.source,
        source_time=float(
            source_time
        ),
        clip_time=float(
            source_time - span.source_in
        ),
        camera_mode=sample.mode,
        camera_yaw_deg=float(
            sample.camera.yaw_deg
        ),
        camera_pitch_deg=float(
            sample.camera.pitch_deg
        ),
        camera_fov_deg=float(
            sample.camera.fov_deg
        ),
    )


def _preview_output_dimensions(
    aspect,
    long_edge,
):
    long_edge = max(
        320,
        int(long_edge),
    )

    if aspect == "16:9":
        return aspect_dimensions(
            aspect,
            width=long_edge,
        )

    return aspect_dimensions(
        aspect,
        height=long_edge,
    )


def prepare_project_preview(
    project: Project,
    *,
    preview_fps=20.0,
    cache_dir=None,
    rebuild_preview=False,
    progress=None,
):
    """
    Ensure every Clip has a panoramic editing preview and build Timeline spans.
    """
    if not project.clips:
        raise ValueError(
            "Project has no Clips to preview"
        )

    profile = PreviewProfile(
        width=1280,
        height=640,
        fps=float(
            preview_fps
        ),
        with_audio=True,
        stabilization_amount=float(project.stabilization_amount),
    )

    entries = {}
    source_durations = {}
    count = len(
        project.clips
    )

    for index, clip in enumerate(
        project.clips,
        start=1,
    ):
        if progress is not None:
            progress(
                f"Clip {index}/{count} — "
                f"{Path(clip.source).name}"
            )

        def cache_progress(event):
            if progress is None:
                return

            message = event.get(
                "message"
            )

            if message:
                progress(
                    f"Clip {index}/{count} — {message}"
                )

        entry = ensure_preview_cache(
            clip.source,
            profile=profile,
            cache_dir=cache_dir,
            rebuild=rebuild_preview,
            progress_callback=cache_progress,
        )

        entries[
            clip.id
        ] = entry

        duration = entry.source_duration

        if duration is None:
            raise RuntimeError(
                "Prepared panoramic preview "
                f"for {clip.id} has no source duration"
            )

        source_durations[
            clip.id
        ] = float(
            duration
        )

    spans = build_project_timeline(
        project,
        source_durations,
    )

    return {
        "entries": entries,
        "source_durations": (
            source_durations
        ),
        "spans": spans,
        "project_duration": float(
            spans[-1].timeline_end
        ),
        "profile": profile,
    }


def run_project_preview(
    project_path,
    *,
    view_long_edge=960,
    preview_fps=20.0,
    cache_dir=None,
    rebuild_preview=False,
    audio_enabled=True,
):
    """
    Open read-only sequential Project Timeline playback.
    """
    project_path = Path(
        project_path
    )
    project = load_project(
        project_path
    )

    if not project.clips:
        raise ValueError(
            "Project has no Clips to preview"
        )

    def prepare(progress):
        return prepare_project_preview(
            project,
            preview_fps=preview_fps,
            cache_dir=cache_dir,
            rebuild_preview=rebuild_preview,
            progress=progress,
        )

    prepared = run_with_loading_screen(
        prepare,
        title="PanoPilot",
        message="Preparing Project preview",
        detail=(
            f"{len(project.clips)} Clip(s)"
        ),
    )

    spans = list(
        prepared["spans"]
    )
    project_duration = float(
        prepared["project_duration"]
    )
    entries = dict(
        prepared["entries"]
    )

    readers = {
        clip_id: PanoramaCacheReader(
            entry
        )
        for clip_id, entry
        in entries.items()
    }

    output_width, output_height = (
        _preview_output_dimensions(
            project.output_aspect,
            view_long_edge,
        )
    )

    try:
        from PySide6.QtCore import (
            QEventLoop,
            QTimer,
            QUrl,
            Qt,
        )
        from PySide6.QtGui import (
            QColor,
            QImage,
            QPainter,
            QPen,
            QPixmap,
        )
        from PySide6.QtWidgets import (
            QApplication,
            QFrame,
            QHBoxLayout,
            QLabel,
            QPushButton,
            QSizePolicy,
            QSlider,
            QStyle,
            QToolButton,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        for reader in readers.values():
            reader.close()

        raise RuntimeError(
            "PySide6 is required for Project preview. "
            "Reinstall PanoPilot with 'pip install -e .'."
        ) from exc

    QMediaPlayer = None
    QAudioOutput = None

    try:
        from PySide6.QtMultimedia import (
            QAudioOutput,
            QMediaPlayer,
        )
    except ImportError:
        pass

    state = {
        "project_time": 0.0,
        "playing": False,
        "at_end": False,
        "last_frame_state": None,
        "last_clip_id": None,
    }

    class ProjectSlider(QSlider):
        def paintEvent(self, event):
            super().paintEvent(
                event
            )

            if project_duration <= 0.0:
                return

            painter = QPainter(
                self
            )
            left = 9
            right = max(
                left + 1,
                self.width() - 9,
            )
            width = right - left

            def x_for_time(value):
                fraction = max(
                    0.0,
                    min(
                        1.0,
                        float(value)
                        / project_duration,
                    ),
                )
                return int(
                    round(
                        left
                        + fraction * width
                    )
                )

            boundary_pen = QPen(
                QColor(
                    90,
                    120,
                    160,
                )
            )
            boundary_pen.setWidth(
                2
            )
            painter.setPen(
                boundary_pen
            )

            for span in spans[:-1]:
                x = x_for_time(
                    span.timeline_end
                )
                painter.drawLine(
                    x,
                    3,
                    x,
                    self.height() - 3,
                )

    class ProjectPreviewWidget(QWidget):
        def __init__(self):
            super().__init__()

            self.setWindowTitle(
                WINDOW_TITLE
            )
            self.setFocusPolicy(
                Qt.FocusPolicy.StrongFocus
            )

            self._play_anchor_project = 0.0
            self._play_anchor_wall = None
            self._audio_clip_id = None

            self.image_label = QLabel()
            self.image_label.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )
            self.image_label.setStyleSheet(
                "background: #111318;"
            )

            self.canvas = QFrame()
            self.canvas.setStyleSheet(
                "background: #111318;"
            )
            self.canvas.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )

            canvas_layout = QHBoxLayout(
                self.canvas
            )
            canvas_layout.setContentsMargins(
                0,
                0,
                0,
                0,
            )
            canvas_layout.addStretch(
                1
            )
            canvas_layout.addWidget(
                self.image_label,
                0,
                Qt.AlignmentFlag.AlignCenter,
            )
            canvas_layout.addStretch(
                1
            )

            self.play_button = QToolButton()
            self.play_button.setIcon(
                self.style().standardIcon(
                    QStyle.StandardPixmap.SP_MediaPlay
                )
            )
            self.play_button.setToolTip(
                "Play / Pause (Space)"
            )
            self.play_button.clicked.connect(
                self._toggle_playback
            )

            self.time_label = QLabel()
            self.time_label.setStyleSheet(
                "font-family: monospace; "
                "font-weight: 600;"
            )

            self.clip_label = QLabel()
            self.clip_label.setStyleSheet(
                "color: palette(mid);"
            )

            self.motion_label = QLabel(
                "Camera Motion: "
                f"{project.camera_motion_easing} "
                f"{int(round(project.camera_motion_strength * 100.0))}%"
            )
            self.motion_label.setStyleSheet(
                "color: palette(mid);"
            )

            self.slider = ProjectSlider(
                Qt.Orientation.Horizontal
            )
            self.slider.setRange(
                0,
                max(
                    1,
                    int(
                        round(
                            project_duration
                            * 1000.0
                        )
                    ),
                ),
            )
            self.slider.sliderPressed.connect(
                self._pause_playback
            )
            self.slider.sliderMoved.connect(
                self._slider_moved
            )
            self.slider.sliderReleased.connect(
                self._slider_released
            )

            transport = QHBoxLayout()
            transport.addWidget(
                self.play_button
            )
            transport.addWidget(
                self.time_label
            )
            transport.addSpacing(
                12
            )
            transport.addWidget(
                self.clip_label,
                1,
            )
            transport.addWidget(
                self.motion_label
            )

            controls = QFrame()
            controls_layout = QVBoxLayout(
                controls
            )
            controls_layout.setContentsMargins(
                8,
                6,
                8,
                6,
            )
            controls_layout.addLayout(
                transport
            )
            controls_layout.addWidget(
                self.slider
            )

            layout = QVBoxLayout(
                self
            )
            layout.setContentsMargins(
                8,
                8,
                8,
                8,
            )
            layout.setSpacing(
                8
            )
            layout.addWidget(
                self.canvas,
                1,
            )
            layout.addWidget(
                controls
            )

            self.play_timer = QTimer(
                self
            )
            self.play_timer.setTimerType(
                Qt.TimerType.PreciseTimer
            )
            self.play_timer.setInterval(
                max(
                    10,
                    int(
                        round(
                            1000.0
                            / max(
                                1.0,
                                float(
                                    preview_fps
                                ),
                            )
                        )
                    ),
                )
            )
            self.play_timer.timeout.connect(
                self._playback_tick
            )

            self.media_player = None
            self.audio_output = None

            if (
                audio_enabled
                and QMediaPlayer is not None
                and QAudioOutput is not None
            ):
                self.audio_output = QAudioOutput(
                    self
                )
                self.media_player = QMediaPlayer(
                    self
                )
                self.media_player.setAudioOutput(
                    self.audio_output
                )

            self.resize(
                max(
                    900,
                    output_width + 32,
                ),
                output_height + 145,
            )

            self._seek_to(
                0.0,
                sync_audio=False,
            )

        def _current_state(self):
            return project_state_at(
                project,
                spans,
                state["project_time"],
            )

        def _frame_for_time(
            self,
            project_time,
        ):
            frame_state = (
                project_state_at(
                    project,
                    spans,
                    project_time,
                )
            )

            clip = project.clip_for_id(
                frame_state.clip_id
            )
            reader = readers[
                frame_state.clip_id
            ]

            panorama, actual_source_time, _index = (
                reader.read_at(
                    frame_state.source_time
                )
            )

            sample = evaluate_clip_view_path(
                clip,
                actual_source_time,
                interpolation=(
                    project.camera_motion_easing
                ),
                strength=(
                    project.camera_motion_strength
                ),
            )

            frame = reframe_equirectangular(
                panorama,
                sample.camera,
                output_width,
                output_height,
            )

            return frame, ProjectPlaybackState(
                project_time=float(
                    project_time
                ),
                project_duration=(
                    project_duration
                ),
                clip_index=(
                    frame_state.clip_index
                ),
                clip_id=(
                    frame_state.clip_id
                ),
                source=(
                    frame_state.source
                ),
                source_time=float(
                    actual_source_time
                ),
                clip_time=float(
                    actual_source_time
                    - spans[
                        frame_state.clip_index
                    ].source_in
                ),
                camera_mode=(
                    sample.mode
                ),
                camera_yaw_deg=float(
                    sample.camera.yaw_deg
                ),
                camera_pitch_deg=float(
                    sample.camera.pitch_deg
                ),
                camera_fov_deg=float(
                    sample.camera.fov_deg
                ),
            )

        def _show_frame(
            self,
            frame,
        ):
            rgb = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB,
            )
            height, width = rgb.shape[:2]

            image = QImage(
                rgb.data,
                width,
                height,
                int(
                    rgb.strides[0]
                ),
                QImage.Format.Format_RGB888,
            ).copy()

            self.image_label.setPixmap(
                QPixmap.fromImage(
                    image
                )
            )
            self.image_label.setFixedSize(
                width,
                height,
            )

        def _sync_audio(
            self,
            frame_state,
            *,
            play=None,
        ):
            if self.media_player is None:
                return

            clip_changed = (
                self._audio_clip_id
                != frame_state.clip_id
            )

            if clip_changed:
                entry = entries[
                    frame_state.clip_id
                ]
                self.media_player.setSource(
                    QUrl.fromLocalFile(
                        str(
                            entry.video_path
                        )
                    )
                )
                self._audio_clip_id = (
                    frame_state.clip_id
                )

            self.media_player.setPosition(
                int(
                    round(
                        frame_state.source_time
                        * 1000.0
                    )
                )
            )

            if play is True:
                self.media_player.play()
            elif play is False:
                self.media_player.pause()

        def _update_labels(
            self,
            frame_state,
        ):
            self.time_label.setText(
                f"{frame_state.project_time:07.3f}s "
                f"/ {project_duration:07.3f}s"
            )

            self.clip_label.setText(
                f"Clip {frame_state.clip_index + 1}/{len(project.clips)} — "
                f"{Path(frame_state.source).name} — "
                f"Clip {frame_state.clip_time:.3f}s — "
                f"Source {frame_state.source_time:.3f}s"
            )

            self.slider.setValue(
                int(
                    round(
                        frame_state.project_time
                        * 1000.0
                    )
                )
            )

        def _seek_to(
            self,
            project_time,
            *,
            sync_audio=True,
        ):
            project_time = max(
                0.0,
                min(
                    float(project_time),
                    project_duration,
                ),
            )

            frame, frame_state = (
                self._frame_for_time(
                    project_time
                )
            )

            state["project_time"] = (
                project_time
            )
            state["last_frame_state"] = (
                frame_state
            )
            state["last_clip_id"] = (
                frame_state.clip_id
            )
            state["at_end"] = (
                project_time
                >= project_duration
                - 0.001
            )

            self._show_frame(
                frame
            )
            self._update_labels(
                frame_state
            )

            if sync_audio:
                self._sync_audio(
                    frame_state,
                    play=(
                        True
                        if state["playing"]
                        else False
                    ),
                )

            return frame_state

        def _start_playback(self):
            if state["playing"]:
                return

            start = project_playback_start_time(
                state["project_time"],
                project_duration,
                tolerance_s=max(
                    0.001,
                    0.51
                    / max(
                        1.0,
                        float(
                            preview_fps
                        ),
                    ),
                ),
            )

            frame_state = self._seek_to(
                start,
                sync_audio=False,
            )

            state["playing"] = True
            state["at_end"] = False
            self._play_anchor_project = (
                state["project_time"]
            )
            self._play_anchor_wall = (
                time.perf_counter()
            )

            self.play_button.setIcon(
                self.style().standardIcon(
                    QStyle.StandardPixmap.SP_MediaPause
                )
            )
            self.play_button.setToolTip(
                "Pause (Space)"
            )

            self._sync_audio(
                frame_state,
                play=True,
            )
            self.play_timer.start()

        def _pause_playback(self):
            if not state["playing"]:
                return

            state["playing"] = False
            self.play_timer.stop()

            self.play_button.setIcon(
                self.style().standardIcon(
                    QStyle.StandardPixmap.SP_MediaPlay
                )
            )
            self.play_button.setToolTip(
                "Play (Space)"
            )

            if self.media_player is not None:
                self.media_player.pause()

        def _toggle_playback(self):
            if state["playing"]:
                self._pause_playback()
            else:
                self._start_playback()

        def _playback_tick(self):
            if not state["playing"]:
                return

            target = (
                self._play_anchor_project
                + (
                    time.perf_counter()
                    - self._play_anchor_wall
                )
            )

            if (
                target
                >= project_duration
            ):
                self._seek_to(
                    project_duration,
                    sync_audio=False,
                )
                self._pause_playback()
                state["at_end"] = True
                return

            previous_clip = (
                state["last_clip_id"]
            )

            frame_state = self._seek_to(
                target,
                sync_audio=False,
            )

            if (
                self.media_player is not None
                and previous_clip
                != frame_state.clip_id
            ):
                self._sync_audio(
                    frame_state,
                    play=True,
                )

        def _slider_moved(
            self,
            value,
        ):
            preview_time = (
                float(value)
                / 1000.0
            )
            self.time_label.setText(
                f"{preview_time:07.3f}s "
                f"/ {project_duration:07.3f}s"
            )

        def _slider_released(self):
            self._pause_playback()
            self._seek_to(
                float(
                    self.slider.value()
                )
                / 1000.0
            )

        def keyPressEvent(
            self,
            event,
        ):
            if (
                event.key()
                == Qt.Key.Key_Space
            ):
                self._toggle_playback()
                event.accept()
                return

            super().keyPressEvent(
                event
            )

        def closeEvent(
            self,
            event,
        ):
            self._pause_playback()

            if self.media_player is not None:
                self.media_player.stop()

            event.accept()
            window_loop.quit()

    app = QApplication.instance()

    if app is None:
        app = QApplication(
            sys.argv[:1]
        )
        app.setApplicationName(
            "PanoPilot"
        )

    app.setQuitOnLastWindowClosed(
        False
    )

    window_loop = QEventLoop()
    widget = ProjectPreviewWidget()
    widget.show()
    widget.raise_()
    widget.activateWindow()
    widget.setFocus()
    window_loop.exec()

    for reader in readers.values():
        reader.close()

    final_state = state[
        "last_frame_state"
    ]

    return {
        "project": str(
            project_path
        ),
        "clip_count": len(
            project.clips
        ),
        "project_duration": (
            project_duration
        ),
        "project_time": float(
            state["project_time"]
        ),
        "at_playback_end": bool(
            state["at_end"]
        ),
        "audio_enabled": bool(
            audio_enabled
        ),
        "camera_motion": {
            "easing": (
                project.camera_motion_easing
            ),
            "strength": float(
                project.camera_motion_strength
            ),
        },
        "last_frame": (
            final_state.to_dict()
            if final_state is not None
            else None
        ),
    }
