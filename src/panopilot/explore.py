"""
Interactive PanoPilot desktop editor.

0.15 moves editing onto a disposable panoramic preview cache and adds real-time
playback.  The original OSV remains immutable and authoritative for final
rendering.

Editing invariant:

    seek / play / drag / wheel / reset = exploration/navigation
    Enter / Return                     = explicit edit (Use this view)

Space is now the conventional Play/Pause shortcut.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import sys
import time

import cv2

from .cache import (
    PanoramaCacheReader,
    PreviewProfile,
    ensure_preview_cache,
)
from .pipeline import render_osv_panorama_frame
from .project import commit_camera_position, load_project, save_project
from .virtual_camera import VirtualCamera, reframe_equirectangular
from .view_path import evaluate_clip_view_path


WINDOW_TITLE = "PanoPilot — Editor"


def format_time(seconds):
    seconds = max(0.0, float(seconds))
    milliseconds = int(round(seconds * 1000.0))
    minutes, milliseconds = divmod(milliseconds, 60_000)
    whole_seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


@dataclass
class ExploreState:
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    fov_deg: float = 90.0
    aspect: str = "16:9"

    initial_yaw_deg: float = 0.0
    initial_pitch_deg: float = 0.0
    initial_fov_deg: float = 90.0
    initial_aspect: str = "16:9"

    pitch_limit_deg: float = 85.0
    min_fov_deg: float = 30.0
    max_fov_deg: float = 120.0

    def __post_init__(self):
        self._validate_aspect(self.aspect)
        self._validate_aspect(self.initial_aspect)
        self.yaw_deg = self._wrap_yaw(self.yaw_deg)
        self.pitch_deg = self._clamp_pitch(self.pitch_deg)
        self.fov_deg = self._clamp_fov(self.fov_deg)

    @staticmethod
    def _validate_aspect(aspect):
        if aspect not in ("16:9", "9:16"):
            raise ValueError("aspect must be '16:9' or '9:16'")

    @staticmethod
    def _wrap_yaw(value):
        return ((float(value) + 180.0) % 360.0) - 180.0

    def _clamp_pitch(self, value):
        return max(-self.pitch_limit_deg, min(self.pitch_limit_deg, float(value)))

    def _clamp_fov(self, value):
        return max(self.min_fov_deg, min(self.max_fov_deg, float(value)))

    def camera(self):
        return VirtualCamera(
            yaw_deg=self.yaw_deg,
            pitch_deg=self.pitch_deg,
            fov_deg=self.fov_deg,
        )

    def snapshot(self):
        return (
            float(self.yaw_deg),
            float(self.pitch_deg),
            float(self.fov_deg),
            str(self.aspect),
        )

    def set_camera(self, camera, *, aspect=None, make_initial=False):
        self.yaw_deg = self._wrap_yaw(camera.yaw_deg)
        self.pitch_deg = self._clamp_pitch(camera.pitch_deg)
        self.fov_deg = self._clamp_fov(camera.fov_deg)

        if aspect is not None:
            self._validate_aspect(aspect)
            self.aspect = aspect

        if make_initial:
            self.initial_yaw_deg = self.yaw_deg
            self.initial_pitch_deg = self.pitch_deg
            self.initial_fov_deg = self.fov_deg
            self.initial_aspect = self.aspect

    def reset(self):
        self.yaw_deg = self._wrap_yaw(self.initial_yaw_deg)
        self.pitch_deg = self._clamp_pitch(self.initial_pitch_deg)
        self.fov_deg = self._clamp_fov(self.initial_fov_deg)
        self.aspect = self.initial_aspect

    def set_aspect(self, aspect):
        self._validate_aspect(aspect)
        self.aspect = aspect

    def apply_drag(self, dx_pixels, dy_pixels, view_width):
        view_width = max(1.0, float(view_width))
        deg_per_pixel = self.fov_deg / view_width
        self.yaw_deg = self._wrap_yaw(
            self.yaw_deg - float(dx_pixels) * deg_per_pixel
        )
        self.pitch_deg = self._clamp_pitch(
            self.pitch_deg + float(dy_pixels) * deg_per_pixel
        )

    def apply_wheel_steps(self, steps):
        self.fov_deg = self._clamp_fov(
            self.fov_deg * math.pow(0.90, float(steps))
        )


class ExploreWindow:
    def __init__(
        self,
        panorama,
        *,
        state,
        source_time,
        source_duration=None,
        commit_callback=None,
        seek_callback=None,
        marker_times=None,
        seek_step_seconds=0.1,
        playback_fps=20.0,
        cache_media_path=None,
        audio_enabled=True,
        landscape_size=(800, 450),
        portrait_size=(450, 800),
        show_hud=True,
    ):
        if panorama is None:
            raise ValueError("panorama is required")

        self.panorama = panorama
        self.state = state
        self.source_duration = (
            max(0.0, float(source_duration))
            if source_duration is not None else None
        )
        self.source_time = self._clamp_time(source_time)
        self.commit_callback = commit_callback
        self.seek_callback = seek_callback
        self.marker_times = sorted(float(v) for v in (marker_times or []))
        self.seek_step_seconds = max(0.001, float(seek_step_seconds))
        self.playback_fps = max(1.0, float(playback_fps))
        self.cache_media_path = (
            str(cache_media_path) if cache_media_path is not None else None
        )
        self.audio_enabled = bool(audio_enabled)
        self.landscape_size = tuple(int(v) for v in landscape_size)
        self.portrait_size = tuple(int(v) for v in portrait_size)
        self.show_hud = bool(show_hud)
        self.last_render_seconds = None
        self.last_seek_seconds = None
        self.last_commit = None
        self.last_committed_snapshot = None
        self.playing = False
        self.audio_clock = "not-started"

    def _clamp_time(self, source_time):
        value = max(0.0, float(source_time))
        if self.source_duration is not None:
            value = min(value, self.source_duration)
        return value

    @property
    def view_size(self):
        return self.landscape_size if self.state.aspect == "16:9" else self.portrait_size

    @staticmethod
    def wheel_steps(delta_y):
        delta_y = float(delta_y)
        return delta_y / 120.0 if delta_y else 0.0

    @property
    def has_uncommitted_changes(self):
        if self.last_committed_snapshot is None:
            return True
        current = self.state.snapshot()
        saved = self.last_committed_snapshot
        numeric_delta = max(
            abs(current[0] - saved[0]),
            abs(current[1] - saved[1]),
            abs(current[2] - saved[2]),
        )
        return numeric_delta > 1e-6 or current[3] != saved[3]

    def use_this_view(self):
        if self.commit_callback is None:
            raise RuntimeError("No Camera Position persistence callback was configured")
        result = self.commit_callback(
            source_time=self.source_time,
            yaw_deg=self.state.yaw_deg,
            pitch_deg=self.state.pitch_deg,
            fov_deg=self.state.fov_deg,
            aspect=self.state.aspect,
        )
        self.last_commit = result
        self.last_committed_snapshot = self.state.snapshot()
        if "marker_times" in result:
            self.marker_times = sorted(float(v) for v in result["marker_times"])
        return result

    def seek(self, source_time):
        target = self._clamp_time(source_time)
        if self.seek_callback is None:
            self.source_time = target
            self.last_commit = None
            self.last_committed_snapshot = None
            return {"source_time": target, "camera": self.state.camera()}

        started = time.perf_counter()
        result = self.seek_callback(target)
        self.last_seek_seconds = time.perf_counter() - started

        panorama = result.get("panorama")
        camera = result.get("camera")
        if panorama is None:
            raise RuntimeError("Seek callback did not return a panorama")
        if camera is None:
            raise RuntimeError("Seek callback did not return a Virtual Camera")

        self.panorama = panorama
        self.source_time = self._clamp_time(result.get("source_time", target))
        self.state.set_camera(
            camera,
            aspect=result.get("aspect", self.state.aspect),
            make_initial=True,
        )
        if result.get("marker_times") is not None:
            self.marker_times = sorted(float(v) for v in result["marker_times"])
        self.last_commit = None
        self.last_committed_snapshot = None
        return result

    def step_time(self, direction):
        direction = -1.0 if float(direction) < 0 else 1.0
        return self.seek(self.source_time + direction * self.seek_step_seconds)

    def _draw_hud(self, frame):
        if not self.show_hud:
            return frame
        rendered = frame.copy()

        if self.playing:
            status = "PLAYBACK — persisted View Path"
        elif self.last_commit is None:
            status = "EXPLORE — changes are not saved"
        elif self.has_uncommitted_changes:
            status = (
                f"Camera Position {self.last_commit['position_number']:02d} saved "
                "— exploring new changes"
            )
        else:
            action = "created" if self.last_commit["created"] else "updated"
            status = (
                f"Camera Position {self.last_commit['position_number']:02d} "
                f"{action} @ {self.source_time:.3f}s"
            )

        duration_text = (
            format_time(self.source_duration)
            if self.source_duration is not None else "--:--.---"
        )
        lines = [
            status,
            f"time {format_time(self.source_time)} / {duration_text}   markers {len(self.marker_times)}",
            (
                f"yaw {self.state.yaw_deg:+.1f}°   pitch {self.state.pitch_deg:+.1f}°   "
                f"FOV {self.state.fov_deg:.1f}°   {self.state.aspect}"
            ),
            (
                "drag: look   wheel: zoom   Enter: Use this view   Space: Play/Pause   "
                "←/→: seek   R: reset   1/2: aspect"
            ),
        ]

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.43
        thickness = 1
        line_height = 21
        padding = 9
        max_width = max(
            cv2.getTextSize(line, font, font_scale, thickness)[0][0]
            for line in lines
        )
        overlay = rendered.copy()
        cv2.rectangle(
            overlay,
            (8, 8),
            (
                min(rendered.shape[1] - 8, 8 + max_width + 2 * padding),
                8 + len(lines) * line_height + padding,
            ),
            (0, 0, 0),
            -1,
        )
        cv2.addWeighted(overlay, 0.58, rendered, 0.42, 0, rendered)
        for index, line in enumerate(lines):
            cv2.putText(
                rendered,
                line,
                (8 + padding, 8 + padding + 14 + index * line_height),
                font,
                font_scale,
                (255, 255, 255),
                thickness,
                cv2.LINE_AA,
            )
        return rendered

    def render(self):
        width, height = self.view_size
        started = time.perf_counter()
        frame = reframe_equirectangular(
            self.panorama,
            self.state.camera(),
            width,
            height,
        )
        self.last_render_seconds = time.perf_counter() - started
        return self._draw_hud(frame)

    def run(self):
        try:
            from PySide6.QtCore import QTimer, QUrl, Qt
            from PySide6.QtGui import (
                QColor, QImage, QKeyEvent, QMouseEvent,
                QPainter, QPen, QPixmap, QWheelEvent,
            )
            from PySide6.QtWidgets import (
                QApplication, QHBoxLayout, QLabel, QPushButton,
                QSlider, QVBoxLayout, QWidget,
            )
        except ImportError as exc:
            raise RuntimeError(
                "PySide6 is required for the interactive desktop editor. "
                "Reinstall PanoPilot with 'pip install -e .'."
            ) from exc

        # Qt Multimedia is optional at runtime.  When available, its playback
        # position is the master clock and it also plays the source audio from
        # the cached MP4.  The monotonic clock remains a deterministic fallback.
        QMediaPlayer = None
        QAudioOutput = None
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        except ImportError:
            pass

        outer = self

        class TimeSlider(QSlider):
            def paintEvent(self, event):
                super().paintEvent(event)
                if (
                    outer.source_duration is None
                    or outer.source_duration <= 0.0
                    or not outer.marker_times
                ):
                    return
                painter = QPainter(self)
                pen = QPen(QColor(220, 70, 70))
                pen.setWidth(2)
                painter.setPen(pen)
                left = 9
                right = max(left + 1, self.width() - 9)
                width = right - left
                for marker in outer.marker_times:
                    fraction = max(0.0, min(1.0, marker / outer.source_duration))
                    x = int(round(left + fraction * width))
                    painter.drawLine(x, 2, x, max(2, self.height() - 3))

        class EditorWidget(QWidget):
            def __init__(self):
                super().__init__()
                self.setWindowTitle(WINDOW_TITLE)
                self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                self._dragging = False
                self._last_pos = None
                self._play_anchor_wall = None
                self._play_anchor_source = None

                self.image_label = QLabel()
                self.image_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                self.time_label = QLabel()
                self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.play_button = QPushButton("Play")
                self.play_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                self.play_button.clicked.connect(self._toggle_playback)

                self.slider = TimeSlider(Qt.Orientation.Horizontal)
                self.slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                duration_ms = int(round(max(
                    outer.source_duration or 0.0,
                    outer.source_time,
                ) * 1000.0))
                self.slider.setRange(0, max(1, duration_ms))
                self.slider.setValue(int(round(outer.source_time * 1000.0)))
                self.slider.sliderMoved.connect(self._slider_moved)
                self.slider.sliderPressed.connect(self._pause_playback)
                self.slider.sliderReleased.connect(self._slider_released)

                controls = QHBoxLayout()
                controls.addWidget(self.play_button)
                controls.addWidget(self.time_label, 1)

                layout = QVBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 4)
                layout.setSpacing(2)
                layout.addWidget(self.image_label)
                layout.addLayout(controls)
                layout.addWidget(self.slider)

                self.image_label.mousePressEvent = self._image_mouse_press
                self.image_label.mouseReleaseEvent = self._image_mouse_release
                self.image_label.mouseMoveEvent = self._image_mouse_move
                self.image_label.wheelEvent = self._image_wheel

                self.play_timer = QTimer(self)
                self.play_timer.setTimerType(Qt.TimerType.PreciseTimer)
                self.play_timer.setInterval(max(10, int(round(1000.0 / outer.playback_fps))))
                self.play_timer.timeout.connect(self._playback_tick)

                self.media_player = None
                self.audio_output = None
                if (
                    QMediaPlayer is not None
                    and QAudioOutput is not None
                    and outer.cache_media_path
                    and outer.audio_enabled
                ):
                    try:
                        self.media_player = QMediaPlayer(self)
                        self.audio_output = QAudioOutput(self)
                        self.media_player.setAudioOutput(self.audio_output)
                        self.media_player.setSource(
                            QUrl.fromLocalFile(str(Path(outer.cache_media_path).resolve()))
                        )
                        outer.audio_clock = "qt-multimedia"
                    except Exception:
                        self.media_player = None
                        self.audio_output = None
                        outer.audio_clock = "monotonic-fallback"
                else:
                    outer.audio_clock = "monotonic-fallback"

                self._refresh()

            def _duration_text(self):
                return (
                    format_time(outer.source_duration)
                    if outer.source_duration is not None else "--:--.---"
                )

            def _update_time_label(self, preview_time=None):
                value = outer.source_time if preview_time is None else float(preview_time)
                self.time_label.setText(
                    f"{format_time(value)} / {self._duration_text()}   "
                    f"Camera Positions: {len(outer.marker_times)}"
                )

            def _refresh(self):
                frame = outer.render()
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width = rgb.shape[:2]
                image = QImage(
                    rgb.data,
                    width,
                    height,
                    int(rgb.strides[0]),
                    QImage.Format.Format_RGB888,
                ).copy()
                self.image_label.setPixmap(QPixmap.fromImage(image))
                self.image_label.setFixedSize(width, height)
                self.slider.setValue(int(round(outer.source_time * 1000.0)))
                self._update_time_label()
                self.slider.update()
                self.adjustSize()
                self.update()

            def _seek_to(self, seconds):
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                try:
                    outer.seek(seconds)
                    if self.media_player is not None:
                        self.media_player.setPosition(int(round(outer.source_time * 1000.0)))
                    self._refresh()
                finally:
                    QApplication.restoreOverrideCursor()

            def _playback_target_time(self):
                if self.media_player is not None:
                    position = self.media_player.position()
                    if position >= 0:
                        position_s = float(position) / 1000.0
                        # QMediaPlayer may briefly report 0 while an async
                        # local source is loading.  Do not jump the editor
                        # back to zero when playback was started later in the
                        # clip; use the monotonic fallback until the media
                        # clock reaches the requested start position.
                        if (
                            self._play_anchor_source <= 0.25
                            or position_s >= self._play_anchor_source - 0.25
                        ):
                            return position_s
                return (
                    self._play_anchor_source
                    + (time.perf_counter() - self._play_anchor_wall)
                )

            def _start_playback(self):
                if outer.playing:
                    return
                # Playback is navigation, therefore it returns to the persisted
                # path and intentionally discards transient exploration.
                outer.seek(outer.source_time)
                self._refresh()
                outer.playing = True
                self.play_button.setText("Pause")
                self._play_anchor_source = outer.source_time
                self._play_anchor_wall = time.perf_counter()
                if self.media_player is not None:
                    self.media_player.setPosition(int(round(outer.source_time * 1000.0)))
                    self.media_player.play()
                self.play_timer.start()

            def _pause_playback(self):
                if not outer.playing:
                    return
                outer.playing = False
                self.play_timer.stop()
                self.play_button.setText("Play")
                if self.media_player is not None:
                    self.media_player.pause()
                self._refresh()

            def _toggle_playback(self):
                if outer.playing:
                    self._pause_playback()
                else:
                    self._start_playback()

            def _playback_tick(self):
                if not outer.playing:
                    return
                target = self._playback_target_time()
                if (
                    outer.source_duration is not None
                    and target >= outer.source_duration
                ):
                    self._seek_to(outer.source_duration)
                    self._pause_playback()
                    return
                try:
                    outer.seek(target)
                except Exception:
                    self._pause_playback()
                    raise
                self._refresh()

            def _slider_moved(self, value):
                self._update_time_label(float(value) / 1000.0)

            def _slider_released(self):
                self._seek_to(float(self.slider.value()) / 1000.0)

            def _image_mouse_press(self, event: QMouseEvent):
                if event.button() == Qt.MouseButton.LeftButton:
                    self._pause_playback()
                    self._dragging = True
                    self._last_pos = event.position()
                    event.accept()

            def _image_mouse_release(self, event: QMouseEvent):
                if event.button() == Qt.MouseButton.LeftButton:
                    self._dragging = False
                    self._last_pos = None
                    event.accept()

            def _image_mouse_move(self, event: QMouseEvent):
                if self._dragging and self._last_pos is not None:
                    pos = event.position()
                    dx = pos.x() - self._last_pos.x()
                    dy = pos.y() - self._last_pos.y()
                    width, _ = outer.view_size
                    outer.state.apply_drag(dx, dy, width)
                    self._last_pos = pos
                    self._refresh()
                    event.accept()

            def _image_wheel(self, event: QWheelEvent):
                self._pause_playback()
                steps = outer.wheel_steps(event.angleDelta().y())
                if not steps and not event.pixelDelta().isNull():
                    steps = event.pixelDelta().y() / 30.0
                if steps:
                    outer.state.apply_wheel_steps(steps)
                    self._refresh()
                event.accept()

            def keyPressEvent(self, event: QKeyEvent):
                key = event.key()
                if key in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
                    self._pause_playback()
                    self.close()
                    return
                if key == Qt.Key.Key_Space:
                    self._toggle_playback()
                    return
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._pause_playback()
                    outer.use_this_view()
                    self._refresh()
                    return
                if key == Qt.Key.Key_Left:
                    self._pause_playback()
                    self._seek_to(outer.source_time - outer.seek_step_seconds)
                    return
                if key == Qt.Key.Key_Right:
                    self._pause_playback()
                    self._seek_to(outer.source_time + outer.seek_step_seconds)
                    return
                if key == Qt.Key.Key_R:
                    self._pause_playback()
                    outer.state.reset()
                    self._refresh()
                    return
                if key == Qt.Key.Key_1:
                    self._pause_playback()
                    outer.state.set_aspect("16:9")
                    self._refresh()
                    return
                if key == Qt.Key.Key_2:
                    self._pause_playback()
                    outer.state.set_aspect("9:16")
                    self._refresh()
                    return
                if key == Qt.Key.Key_H:
                    outer.show_hud = not outer.show_hud
                    self._refresh()
                    return
                super().keyPressEvent(event)

            def closeEvent(self, event):
                self._pause_playback()
                if self.media_player is not None:
                    self.media_player.stop()
                super().closeEvent(event)

        app = QApplication.instance()
        owns_app = app is None
        if app is None:
            app = QApplication(sys.argv[:1])
            app.setApplicationName("PanoPilot")

        widget = EditorWidget()
        widget.show()
        widget.raise_()
        widget.activateWindow()
        widget.setFocus()

        if owns_app:
            app.exec()
        else:
            while widget.isVisible():
                app.processEvents()
                time.sleep(0.005)

        return {
            "source_time": float(self.source_time),
            "source_duration": self.source_duration,
            "yaw_deg": float(self.state.yaw_deg),
            "pitch_deg": float(self.state.pitch_deg),
            "fov_deg": float(self.state.fov_deg),
            "aspect": self.state.aspect,
            "camera_position_markers": list(self.marker_times),
            "playback_fps": float(self.playback_fps),
            "audio_clock": self.audio_clock,
            "last_render_ms": (
                float(self.last_render_seconds * 1000.0)
                if self.last_render_seconds is not None else None
            ),
            "last_seek_ms": (
                float(self.last_seek_seconds * 1000.0)
                if self.last_seek_seconds is not None else None
            ),
            "last_commit": self.last_commit,
            "has_uncommitted_changes": self.has_uncommitted_changes,
            "ui_backend": "PySide6/Qt",
        }


def explore_osv(
    source,
    *,
    source_time=2.0,
    yaw_deg=None,
    pitch_deg=None,
    fov_deg=None,
    aspect="16:9",
    level_horizon=True,
    level_strength=1.0,
    imu_source="highrate",
    imu_offset_ms=0.0,
    panorama_width=1280,
    panorama_height=640,
    preview_fps=20.0,
    level_smoothing_ms=100.0,
    view_long_edge=800,
    show_hud=True,
    project_path="results/panopilot_project.json",
    seek_step_seconds=0.1,
    cache_dir=None,
    rebuild_preview=False,
    use_preview_cache=True,
    audio_enabled=True,
):
    view_long_edge = int(view_long_edge)
    if view_long_edge < 320:
        raise ValueError("view_long_edge must be at least 320")

    project = load_project(project_path, default_aspect=aspect)
    existing_clip = project.clip_for_source(str(source), create=False)
    path_sample = (
        evaluate_clip_view_path(existing_clip, source_time)
        if existing_clip is not None else None
    )

    initial_yaw = float(yaw_deg) if yaw_deg is not None else (
        float(path_sample.camera.yaw_deg) if path_sample is not None else 0.0
    )
    initial_pitch = float(pitch_deg) if pitch_deg is not None else (
        float(path_sample.camera.pitch_deg) if path_sample is not None else 0.0
    )
    initial_fov = float(fov_deg) if fov_deg is not None else (
        float(path_sample.camera.fov_deg) if path_sample is not None else 90.0
    )
    initial_aspect = project.output_aspect if project.clips else aspect

    cache_entry = None
    cache_reader = None
    source_duration = None
    initial_diagnostics = {}

    if use_preview_cache:
        profile = PreviewProfile(
            width=int(panorama_width),
            height=int(panorama_height),
            fps=float(preview_fps),
            level_horizon=bool(level_horizon),
            level_strength=float(level_strength),
            level_smoothing_ms=float(level_smoothing_ms),
            imu_source=str(imu_source),
            imu_offset_ms=float(imu_offset_ms),
            with_audio=True,
        )

        def progress(event):
            print(event["message"] + "...", flush=True)

        cache_entry = ensure_preview_cache(
            source,
            profile=profile,
            cache_dir=cache_dir,
            rebuild=rebuild_preview,
            progress_callback=progress,
        )
        if cache_entry.reused:
            print(
                f"Using prepared panoramic preview: {cache_entry.video_path}",
                flush=True,
            )
        else:
            print(
                f"Prepared panoramic preview: {cache_entry.video_path}",
                flush=True,
            )

        cache_reader = PanoramaCacheReader(cache_entry)
        panorama, actual_time, _ = cache_reader.read_at(source_time)
        source_time = actual_time
        source_duration = cache_entry.source_duration or cache_reader.media_duration
        initial_diagnostics = {
            "preview_cache": cache_entry.to_dict(),
            "cache_reader_fps": cache_reader.fps,
            "cache_frame_count": cache_reader.frame_count,
        }
    else:
        print(
            f"Preparing panoramic scene at Source Time {float(source_time):.3f}s...",
            flush=True,
        )
        panorama, initial_diagnostics = render_osv_panorama_frame(
            source,
            source_time=source_time,
            width=panorama_width,
            height=panorama_height,
            level_horizon=level_horizon,
            level_strength=level_strength,
            imu_source=imu_source,
            imu_offset_ms=imu_offset_ms,
        )
        source_duration = initial_diagnostics.get("source_duration")
        preview_fps = 1.0

    # The cache represents discrete editing frames.  If the requested time
    # snapped to a nearby cache frame, evaluate the persisted View Path at the
    # exact frame the user is actually seeing.
    path_sample = (
        evaluate_clip_view_path(existing_clip, source_time)
        if existing_clip is not None else None
    )
    initial_yaw = float(yaw_deg) if yaw_deg is not None else (
        float(path_sample.camera.yaw_deg) if path_sample is not None else 0.0
    )
    initial_pitch = float(pitch_deg) if pitch_deg is not None else (
        float(path_sample.camera.pitch_deg) if path_sample is not None else 0.0
    )
    initial_fov = float(fov_deg) if fov_deg is not None else (
        float(path_sample.camera.fov_deg) if path_sample is not None else 90.0
    )

    landscape_size = (
        view_long_edge,
        int(round(view_long_edge * 9.0 / 16.0)),
    )
    portrait_size = (
        int(round(view_long_edge * 9.0 / 16.0)),
        view_long_edge,
    )

    state = ExploreState(
        yaw_deg=initial_yaw,
        pitch_deg=initial_pitch,
        fov_deg=initial_fov,
        aspect=initial_aspect,
        initial_yaw_deg=initial_yaw,
        initial_pitch_deg=initial_pitch,
        initial_fov_deg=initial_fov,
        initial_aspect=initial_aspect,
    )

    def current_clip():
        return project.clip_for_source(str(source), create=False)

    def marker_times():
        clip = current_clip()
        return [] if clip is None else [
            float(position.source_time) for position in clip.camera_positions
        ]

    def commit_callback(*, source_time, yaw_deg, pitch_deg, fov_deg, aspect):
        result = commit_camera_position(
            project,
            source,
            source_time=source_time,
            yaw_deg=yaw_deg,
            pitch_deg=pitch_deg,
            fov_deg=fov_deg,
            output_aspect=aspect,
        )
        save_project(project, project_path)
        return {
            **result,
            "project_path": str(project_path),
            "marker_times": marker_times(),
        }

    def seek_callback(target_time):
        target_time = max(0.0, float(target_time))
        if source_duration is not None:
            target_time = min(target_time, float(source_duration))

        if cache_reader is not None:
            new_panorama, actual_time, frame_index = cache_reader.read_at(target_time)
            target_time = actual_time
            diagnostics = {"cache_frame_index": frame_index}
        else:
            new_panorama, diagnostics = render_osv_panorama_frame(
                source,
                source_time=target_time,
                width=panorama_width,
                height=panorama_height,
                level_horizon=level_horizon,
                level_strength=level_strength,
                imu_source=imu_source,
                imu_offset_ms=imu_offset_ms,
            )

        clip = current_clip()
        if clip is not None:
            sample = evaluate_clip_view_path(clip, target_time)
            camera = sample.camera
            mode = sample.mode
        else:
            camera = VirtualCamera(0.0, 0.0, 90.0)
            mode = "default"

        return {
            "source_time": target_time,
            "panorama": new_panorama,
            "camera": camera,
            "view_path_mode": mode,
            "aspect": project.output_aspect,
            "marker_times": marker_times(),
            "diagnostics": diagnostics,
        }

    window = ExploreWindow(
        panorama,
        state=state,
        source_time=source_time,
        source_duration=source_duration,
        commit_callback=commit_callback,
        seek_callback=seek_callback,
        marker_times=marker_times(),
        seek_step_seconds=seek_step_seconds,
        playback_fps=(cache_reader.fps if cache_reader is not None else preview_fps),
        cache_media_path=(cache_entry.video_path if cache_entry is not None else None),
        audio_enabled=(audio_enabled and cache_entry is not None),
        landscape_size=landscape_size,
        portrait_size=portrait_size,
        show_hud=show_hud,
    )

    try:
        final_state = window.run()
    finally:
        if cache_reader is not None:
            cache_reader.close()

    clip = current_clip()
    return {
        "source": str(source),
        "source_time": float(final_state["source_time"]),
        "project_path": str(project_path),
        "project_exists": Path(project_path).exists(),
        "initial_view_path": path_sample.to_dict() if path_sample is not None else None,
        "camera_position_count": len(clip.camera_positions) if clip is not None else 0,
        "preview_cache": cache_entry.to_dict() if cache_entry is not None else None,
        "panorama": initial_diagnostics,
        "explore_state": final_state,
    }
