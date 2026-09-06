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
from .loading import run_with_loading_screen
from .project import load_project
from .session import ProjectSession
from .virtual_camera import VirtualCamera, reframe_equirectangular
from .view_path import evaluate_clip_view_path


WINDOW_TITLE = "PanoPilot — Editor"


def format_time(seconds):
    seconds = max(0.0, float(seconds))
    milliseconds = int(round(seconds * 1000.0))
    minutes, milliseconds = divmod(milliseconds, 60_000)
    whole_seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def trim_summary_text(trim_in, trim_out):
    trim_in = float(trim_in)
    trim_out = float(trim_out)
    duration = max(0.0, trim_out - trim_in)

    return (
        f"ACTIVE CLIP   "
        f"IN {format_time(trim_in)}   "
        f"OUT {format_time(trim_out)}   "
        f"DURATION {format_time(duration)}"
    )


def compact_trim_labels(trim_in, trim_out):
    trim_in = float(trim_in)
    trim_out = float(trim_out)

    return {
        "in": f"IN  {format_time(trim_in)}",
        "out": f"OUT  {format_time(trim_out)}",
        "duration": (
            f"CLIP  {format_time(max(0.0, trim_out - trim_in))}"
        ),
    }


def compact_camera_text(yaw_deg, pitch_deg, fov_deg, aspect):
    return (
        f"Yaw {float(yaw_deg):+.1f}°   "
        f"Pitch {float(pitch_deg):+.1f}°   "
        f"FOV {float(fov_deg):.1f}°   "
        f"{aspect}"
    )


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
        save_callback=None,
        undo_callback=None,
        redo_callback=None,
        delete_callback=None,
        aspect_callback=None,
        discard_callback=None,
        trim_in_callback=None,
        trim_out_callback=None,
        clear_trim_callback=None,
        motion_callback=None,
        marker_times=None,
        dormant_marker_times=None,
        trim_in_source_time=0.0,
        trim_out_source_time=None,
        camera_motion_easing="smooth",
        camera_motion_strength=1.0,
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
        self.save_callback = save_callback
        self.undo_callback = undo_callback
        self.redo_callback = redo_callback
        self.delete_callback = delete_callback
        self.aspect_callback = aspect_callback
        self.discard_callback = discard_callback
        self.trim_in_callback = trim_in_callback
        self.trim_out_callback = trim_out_callback
        self.clear_trim_callback = clear_trim_callback
        self.motion_callback = motion_callback
        self.camera_motion_easing = str(
            camera_motion_easing
        )
        self.camera_motion_strength = max(
            0.0,
            min(
                1.0,
                float(camera_motion_strength),
            ),
        )
        self.marker_times = sorted(float(v) for v in (marker_times or []))
        self.dormant_marker_times = sorted(
            float(v) for v in (dormant_marker_times or [])
        )
        self.trim_in_source_time = max(0.0, float(trim_in_source_time))
        self.trim_out_source_time = (
            float(trim_out_source_time)
            if trim_out_source_time is not None
            else None
        )
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
        self.last_edit_message = None
        self.project_dirty = False
        self.can_undo = False
        self.can_redo = False
        self.undo_label = None
        self.redo_label = None
        self.saved_this_session = False
        self.playing = False
        self.playback_view_mode = "persisted-path"
        self.transient_playback_camera = None
        self.transient_playback_aspect = None
        self.at_playback_end = False
        self.audio_clock = "not-started"

    def _clamp_time(self, source_time):
        value = max(0.0, float(source_time))
        if self.source_duration is not None:
            value = min(value, self.source_duration)
        return value

    @property
    def trim_start(self):
        return float(self.trim_in_source_time)

    @property
    def trim_end(self):
        if self.trim_out_source_time is not None:
            return float(self.trim_out_source_time)
        if self.source_duration is not None:
            return float(self.source_duration)
        return self.trim_start

    @property
    def clip_duration(self):
        return max(0.0, self.trim_end - self.trim_start)

    def clip_local_time(self, source_time=None):
        value = self.source_time if source_time is None else float(source_time)
        return value - self.trim_start

    def source_time_inside_trim(self, source_time=None):
        value = self.source_time if source_time is None else float(source_time)
        tolerance = max(0.001, 0.51 / self.playback_fps)
        return (
            value >= self.trim_start - tolerance
            and value <= self.trim_end + tolerance
        )

    def playback_start_time(self):
        """Restart at Clip In when Play is pressed at/after Clip Out."""
        if self.at_playback_end:
            return self.trim_start

        tolerance = max(0.001, 0.51 / self.playback_fps)
        if self.source_time < self.trim_start - tolerance:
            return self.trim_start
        if self.source_time >= self.trim_end - tolerance:
            return self.trim_start
        return self.source_time

    @property
    def view_size(self):
        return self.landscape_size if self.state.aspect == "16:9" else self.portrait_size

    @staticmethod
    def wheel_steps(delta_y):
        delta_y = float(delta_y)
        return delta_y / 120.0 if delta_y else 0.0

    @property
    def exploration_differs_from_initial(self):
        """
        True only when the current transient camera differs from the camera
        loaded for this Source Time.

        Unlike ``camera_exploration_changed`` this does not assume that a
        missing prior commit means the view has changed.
        """
        current = self.state.snapshot()
        initial = (
            float(self.state.initial_yaw_deg),
            float(self.state.initial_pitch_deg),
            float(self.state.initial_fov_deg),
            str(self.state.initial_aspect),
        )

        numeric_delta = max(
            abs(current[0] - initial[0]),
            abs(current[1] - initial[1]),
            abs(current[2] - initial[2]),
        )

        return (
            numeric_delta > 1e-6
            or current[3] != initial[3]
        )

    @property
    def camera_position_count(self):
        return int(
            len(self.marker_times)
            + len(self.dormant_marker_times)
        )

    @property
    def can_preview_transient_hold(self):
        """
        A zero-View-Path Clip may play from the currently explored camera
        without creating an edit. The view remains preview-only until Set
        Camera is used.
        """
        return (
            self.camera_position_count == 0
            and self.exploration_differs_from_initial
        )

    @property
    def camera_exploration_changed(self):
        """
        Whether the transient Virtual Camera differs from the last committed
        view.

        This is deliberately NOT project dirty state and never requires Save.
        """
        if self.last_committed_snapshot is None:
            return True

        current = self.state.snapshot()
        saved = self.last_committed_snapshot

        numeric_delta = max(
            abs(current[0] - saved[0]),
            abs(current[1] - saved[1]),
            abs(current[2] - saved[2]),
        )

        return (
            numeric_delta > 1e-6
            or current[3] != saved[3]
        )

    @property
    def has_uncommitted_changes(self):
        """Deprecated compatibility alias; use camera_exploration_changed."""
        return self.camera_exploration_changed

    def _apply_project_state(self, result, *, restore_camera=False):
        if result is None:
            return None

        if "dirty" in result:
            self.project_dirty = bool(result["dirty"])
        if "can_undo" in result:
            self.can_undo = bool(result["can_undo"])
        if "can_redo" in result:
            self.can_redo = bool(result["can_redo"])
        if "undo_label" in result:
            self.undo_label = result["undo_label"]
        if "redo_label" in result:
            self.redo_label = result["redo_label"]

        if result.get("marker_times") is not None:
            self.marker_times = sorted(
                float(value)
                for value in result["marker_times"]
            )

        if result.get("dormant_marker_times") is not None:
            self.dormant_marker_times = sorted(
                float(value)
                for value in result["dormant_marker_times"]
            )

        trim_changed = False
        if result.get("trim_in_source_time") is not None:
            self.trim_in_source_time = float(
                result["trim_in_source_time"]
            )
            trim_changed = True
        if "trim_out_source_time" in result:
            self.trim_out_source_time = (
                float(result["trim_out_source_time"])
                if result["trim_out_source_time"] is not None
                else None
            )
            trim_changed = True

        if trim_changed:
            self.at_playback_end = (
                self.source_time >= self.trim_end - 1e-6
            )

        if result.get("camera_motion_easing") is not None:
            self.camera_motion_easing = str(
                result["camera_motion_easing"]
            )

        if result.get("camera_motion_strength") is not None:
            self.camera_motion_strength = max(
                0.0,
                min(
                    1.0,
                    float(
                        result["camera_motion_strength"]
                    ),
                ),
            )

        if restore_camera and result.get("camera") is not None:
            self.state.set_camera(
                result["camera"],
                aspect=result.get(
                    "aspect",
                    self.state.aspect,
                ),
                make_initial=True,
            )
            self.last_committed_snapshot = self.state.snapshot()

        label = result.get("label")
        if result.get("changed") and label:
            self.last_edit_message = str(label)

        return result

    def save_project(self):
        if self.save_callback is None:
            raise RuntimeError(
                "No project save callback was configured"
            )

        result = self.save_callback()
        self._apply_project_state(result)
        self.saved_this_session = bool(result.get("saved"))
        self.last_edit_message = "Project saved"
        return result

    def undo_edit(self):
        if self.undo_callback is None:
            raise RuntimeError(
                "No undo callback was configured"
            )

        result = self.undo_callback(
            source_time=self.source_time
        )
        self._apply_project_state(
            result,
            restore_camera=True,
        )
        self.last_commit = None
        return result

    def redo_edit(self):
        if self.redo_callback is None:
            raise RuntimeError(
                "No redo callback was configured"
            )

        result = self.redo_callback(
            source_time=self.source_time
        )
        self._apply_project_state(
            result,
            restore_camera=True,
        )
        self.last_commit = None
        return result

    def delete_current_position(self):
        if self.delete_callback is None:
            raise RuntimeError(
                "No Camera Position delete callback was configured"
            )

        result = self.delete_callback(
            source_time=self.source_time
        )
        self._apply_project_state(
            result,
            restore_camera=True,
        )
        self.last_commit = None

        operation = result.get("result") or {}
        if (
            not result.get("changed")
            and not operation.get("deleted")
        ):
            self.last_edit_message = (
                "No Camera Position at current frame"
            )

        return result

    def set_output_aspect(self, aspect):
        if self.aspect_callback is None:
            self.state.set_aspect(aspect)
            return {
                "changed": False,
                "aspect": aspect,
            }

        result = self.aspect_callback(
            aspect=aspect,
            source_time=self.source_time,
        )
        self._apply_project_state(result)

        self.state.set_aspect(aspect)
        self.state.initial_aspect = aspect
        self.last_commit = None
        return result

    def set_camera_motion(
        self,
        *,
        easing=None,
        strength=None,
    ):
        easing = (
            self.camera_motion_easing
            if easing is None
            else str(easing)
        )
        strength = (
            self.camera_motion_strength
            if strength is None
            else float(strength)
        )

        if self.motion_callback is None:
            self.camera_motion_easing = easing
            self.camera_motion_strength = max(
                0.0,
                min(
                    1.0,
                    strength,
                ),
            )
            return {
                "changed": False,
                "camera_motion_easing": (
                    self.camera_motion_easing
                ),
                "camera_motion_strength": (
                    self.camera_motion_strength
                ),
            }

        result = self.motion_callback(
            easing=easing,
            strength=strength,
            source_time=self.source_time,
        )
        self._apply_project_state(
            result,
            restore_camera=True,
        )
        self.last_commit = None
        self.last_edit_message = (
            "Camera motion "
            f"{self.camera_motion_easing} "
            f"{int(round(self.camera_motion_strength * 100.0))}%"
        )
        return result

    def set_trim_in_here(self):
        if self.trim_in_callback is None:
            raise RuntimeError(
                "No Clip In callback was configured"
            )

        result = self.trim_in_callback(
            source_time=self.source_time
        )
        self._apply_project_state(
            result,
            restore_camera=True,
        )
        self.last_commit = None
        self.last_edit_message = (
            f"Clip In set: {format_time(self.trim_start)} | "
            f"Out: {format_time(self.trim_end)} | "
            f"Duration: {format_time(self.clip_duration)}"
        )
        return result

    def set_trim_out_here(self):
        if self.trim_out_callback is None:
            raise RuntimeError(
                "No Clip Out callback was configured"
            )

        result = self.trim_out_callback(
            source_time=self.source_time
        )
        self._apply_project_state(
            result,
            restore_camera=True,
        )
        self.last_commit = None
        self.last_edit_message = (
            f"Clip Out set: {format_time(self.trim_end)} | "
            f"In: {format_time(self.trim_start)} | "
            f"Duration: {format_time(self.clip_duration)}"
        )
        return result

    def clear_trim(self):
        if self.clear_trim_callback is None:
            raise RuntimeError(
                "No Clear Trim callback was configured"
            )

        result = self.clear_trim_callback(
            source_time=self.source_time
        )
        self._apply_project_state(
            result,
            restore_camera=True,
        )
        self.last_commit = None
        self.last_edit_message = (
            f"Clip trim cleared | "
            f"In: {format_time(self.trim_start)} | "
            f"Out: {format_time(self.trim_end)} | "
            f"Duration: {format_time(self.clip_duration)}"
        )
        return result

    def discard_unsaved(self):
        if self.discard_callback is None:
            return None

        result = self.discard_callback(
            source_time=self.source_time
        )
        self._apply_project_state(
            result,
            restore_camera=True,
        )
        self.last_commit = None
        self.last_edit_message = "Unsaved changes discarded"
        return result

    def use_this_view(self):
        """
        Set the current Virtual Camera as a Camera Position.

        In the normal desktop editor, Camera Position creation/update is an
        explicit persistence boundary: after the project transaction succeeds,
        the project is atomically saved immediately. This prevents a visually
        created Camera Position from disappearing merely because the user later
        closes the Clip Editor without a separate Save action.

        Undo history remains available. Undoing an auto-saved Camera Position
        makes the project Modified again until saved/redone.
        """
        if self.commit_callback is None:
            raise RuntimeError(
                "No Camera Position persistence callback was configured"
            )

        self.end_playback_view()

        result = self.commit_callback(
            source_time=self.source_time,
            yaw_deg=self.state.yaw_deg,
            pitch_deg=self.state.pitch_deg,
            fov_deg=self.state.fov_deg,
            aspect=self.state.aspect,
        )

        self.last_commit = result
        self.last_committed_snapshot = self.state.snapshot()
        self._apply_project_state(result)

        autosaved = False

        if (
            result.get("changed")
            and self.save_callback is not None
        ):
            save_result = self.save_callback()
            self._apply_project_state(
                save_result
            )
            self.saved_this_session = bool(
                save_result.get("saved")
            )
            autosaved = self.saved_this_session

        position_number = result.get(
            "position_number"
        )

        if position_number is not None:
            action = (
                "created"
                if result.get("created")
                else "updated"
            )
            persistence = (
                "saved"
                if autosaved
                else "set"
            )
            self.last_edit_message = (
                f"Camera Position {int(position_number):02d} "
                f"{action} and {persistence} @ "
                f"{format_time(self.source_time)}"
            )

        return {
            **result,
            "autosaved": bool(autosaved),
        }

    def begin_playback_view(self):
        """
        Select how the Virtual Camera should behave for this playback run.

        - If the Clip already has Camera Positions, playback always follows the
          persisted View Path.
        - If the Clip has zero Camera Positions and the user has explored to a
          different view, playback holds that transient view without saving it.

        This preserves "exploration is not editing" while avoiding the
        surprising snap back to yaw=0/pitch=0/FOV=90 when Play is pressed.
        """
        if self.can_preview_transient_hold:
            self.playback_view_mode = (
                "transient-hold"
            )
            self.transient_playback_camera = (
                self.state.camera()
            )
            self.transient_playback_aspect = (
                self.state.aspect
            )
        else:
            self.playback_view_mode = (
                "persisted-path"
            )
            self.transient_playback_camera = None
            self.transient_playback_aspect = None

        return self.playback_view_mode

    def end_playback_view(self):
        self.playback_view_mode = (
            "persisted-path"
        )
        self.transient_playback_camera = None
        self.transient_playback_aspect = None

    def seek_for_playback(self, source_time):
        """
        Advance playback while respecting the selected playback view mode.
        """
        hold_camera = (
            self.transient_playback_camera
            if self.playback_view_mode
            == "transient-hold"
            else None
        )
        hold_aspect = (
            self.transient_playback_aspect
            if hold_camera is not None
            else None
        )

        result = self.seek(
            source_time
        )

        if hold_camera is not None:
            self.state.set_camera(
                hold_camera,
                aspect=hold_aspect,
                make_initial=False,
            )

        return result

    def seek(self, source_time):
        target = self._clamp_time(source_time)
        requested_at_end = target >= self.trim_end - 1e-6
        if self.seek_callback is None:
            self.source_time = target
            self.at_playback_end = requested_at_end
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
        self._apply_project_state(result)
        # Preserve the logical playhead-end request even when the cached
        # panorama snapped to an earlier physical frame.
        self.at_playback_end = requested_at_end
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

        if (
            self.playing
            and self.playback_view_mode
            == "transient-hold"
        ):
            status = (
                "PREVIEW PLAYBACK — unsaved camera hold; "
                "Set Camera to persist"
            )
        elif self.playing:
            status = "PLAYBACK — Clip View Path"
        elif self.project_dirty:
            if self.last_edit_message:
                status = (
                    f"PROJECT MODIFIED — {self.last_edit_message} — Ctrl+S to save"
                )
            else:
                status = "PROJECT MODIFIED — Ctrl+S to save"
        else:
            status = (
                "EXPLORE — project saved; transient camera movement "
                "does not require Save"
            )

        lines = [
            status,
            compact_camera_text(
                self.state.yaw_deg,
                self.state.pitch_deg,
                self.state.fov_deg,
                self.state.aspect,
            ),
        ]

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.46
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
            from PySide6.QtCore import QEventLoop, QTimer, QUrl, Qt
            from PySide6.QtGui import (
                QColor, QImage, QKeyEvent, QMouseEvent,
                QPainter, QPen, QPixmap, QWheelEvent,
            )
            from PySide6.QtWidgets import (
                QApplication,
                QComboBox,
                QFrame,
                QHBoxLayout,
                QLabel,
                QMessageBox,
                QPushButton,
                QSizePolicy,
                QSlider,
                QStyle,
                QToolButton,
                QVBoxLayout,
                QWidget,
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
            def __init__(self, orientation):
                super().__init__(orientation)
                # Reserve room for explicit IN / OUT flags above the normal
                # slider groove and handle.
                self.setMinimumHeight(46)

            def paintEvent(self, event):
                super().paintEvent(event)

                if (
                    outer.source_duration is None
                    or outer.source_duration <= 0.0
                ):
                    return

                painter = QPainter(self)

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
                            / outer.source_duration,
                        ),
                    )
                    return int(
                        round(
                            left
                            + fraction * width
                        )
                    )

                trim_left = x_for_time(
                    outer.trim_start
                )
                trim_right = x_for_time(
                    outer.trim_end
                )

                # A deliberate, strong visual hierarchy:
                # gray = source outside Clip;
                # blue band = active Clip;
                # red = active Camera Position;
                # muted gray = dormant Camera Position.
                inactive = QColor(
                    85,
                    85,
                    85,
                    70,
                )
                active_band = QColor(
                    70,
                    145,
                    230,
                    90,
                )

                band_top = 20
                band_height = max(
                    8,
                    self.height() - 25,
                )

                painter.fillRect(
                    left,
                    band_top,
                    max(0, trim_left - left),
                    band_height,
                    inactive,
                )
                painter.fillRect(
                    trim_left,
                    band_top,
                    max(1, trim_right - trim_left),
                    band_height,
                    active_band,
                )
                painter.fillRect(
                    trim_right,
                    band_top,
                    max(0, right - trim_right),
                    band_height,
                    inactive,
                )

                dormant_pen = QPen(
                    QColor(130, 130, 130)
                )
                dormant_pen.setWidth(2)
                painter.setPen(dormant_pen)

                for marker in outer.dormant_marker_times:
                    x = x_for_time(marker)
                    painter.drawLine(
                        x,
                        band_top,
                        x,
                        self.height() - 2,
                    )

                active_pen = QPen(
                    QColor(220, 70, 70)
                )
                active_pen.setWidth(3)
                painter.setPen(active_pen)

                for marker in outer.marker_times:
                    x = x_for_time(marker)
                    painter.drawLine(
                        x,
                        band_top,
                        x,
                        self.height() - 2,
                    )

                boundary = QColor(
                    45,
                    105,
                    205,
                )
                trim_pen = QPen(boundary)
                trim_pen.setWidth(4)
                painter.setPen(trim_pen)
                painter.drawLine(
                    trim_left,
                    17,
                    trim_left,
                    self.height() - 1,
                )
                painter.drawLine(
                    trim_right,
                    17,
                    trim_right,
                    self.height() - 1,
                )

                # Flag boxes are intentionally larger than the boundary line
                # so there is no ambiguity about which mark is IN vs OUT.
                flag_width = 34
                flag_height = 17

                in_x = max(
                    left,
                    min(
                        right - flag_width,
                        trim_left - flag_width // 2,
                    ),
                )
                out_x = max(
                    left,
                    min(
                        right - flag_width,
                        trim_right - flag_width // 2,
                    ),
                )

                painter.fillRect(
                    in_x,
                    0,
                    flag_width,
                    flag_height,
                    boundary,
                )
                painter.fillRect(
                    out_x,
                    0,
                    flag_width,
                    flag_height,
                    boundary,
                )

                painter.setPen(
                    QPen(QColor(255, 255, 255))
                )
                painter.drawText(
                    in_x,
                    0,
                    flag_width,
                    flag_height,
                    int(
                        Qt.AlignmentFlag.AlignCenter
                    ),
                    "IN",
                )
                painter.drawText(
                    out_x,
                    0,
                    flag_width,
                    flag_height,
                    int(
                        Qt.AlignmentFlag.AlignCenter
                    ),
                    "OUT",
                )

        class EditorWidget(QWidget):
            def __init__(self):
                super().__init__()
                self.setWindowTitle(WINDOW_TITLE)
                self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                self._dragging = False
                self._last_pos = None
                self._play_anchor_wall = None
                self._play_anchor_source = None

                # ---------------------------------------------------------
                # Media canvas
                # ---------------------------------------------------------
                self.image_label = QLabel()
                self.image_label.setFocusPolicy(
                    Qt.FocusPolicy.NoFocus
                )
                self.image_label.setAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )
                self.image_label.setStyleSheet(
                    "background: #111318;"
                )

                self.canvas = QFrame()
                self.canvas.setFrameShape(
                    QFrame.Shape.NoFrame
                )
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
                canvas_layout.addStretch(1)
                canvas_layout.addWidget(
                    self.image_label,
                    0,
                    Qt.AlignmentFlag.AlignCenter,
                )
                canvas_layout.addStretch(1)

                # ---------------------------------------------------------
                # Compact status readouts
                # ---------------------------------------------------------
                self.time_label = QLabel()
                self.time_label.setAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )
                self.time_label.setStyleSheet(
                    "font-family: monospace; font-weight: 600;"
                )

                self.clip_time_label = QLabel()
                self.clip_time_label.setAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )
                self.clip_time_label.setStyleSheet(
                    "color: palette(mid);"
                )

                self.project_status_label = QLabel(
                    "Saved"
                )
                self.project_status_label.setAlignment(
                    Qt.AlignmentFlag.AlignRight
                    | Qt.AlignmentFlag.AlignVCenter
                )
                self.project_status_label.setMinimumWidth(
                    78
                )

                self.camera_position_label = QLabel(
                    "CAM 0"
                )
                self.camera_position_label.setAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )
                self.camera_position_label.setMinimumWidth(
                    58
                )
                self.camera_position_label.setToolTip(
                    "Saved/working Camera Positions in this Clip"
                )

                self.camera_label = QLabel()
                self.camera_label.setAlignment(
                    Qt.AlignmentFlag.AlignRight
                    | Qt.AlignmentFlag.AlignVCenter
                )
                self.camera_label.setStyleSheet(
                    "color: palette(mid);"
                )

                self.motion_combo = QComboBox()
                self.motion_combo.setFocusPolicy(
                    Qt.FocusPolicy.NoFocus
                )
                self.motion_combo.setToolTip(
                    "Camera transition easing preset"
                )

                motion_choices = [
                    ("Smooth", "smooth"),
                    ("Ease In + Out", "ease-in-out"),
                    ("Ease In", "ease-in"),
                    ("Ease Out", "ease-out"),
                    ("Linear", "linear"),
                ]

                for label, value in motion_choices:
                    self.motion_combo.addItem(
                        label,
                        value,
                    )

                current_motion_index = (
                    self.motion_combo.findData(
                        outer.camera_motion_easing
                    )
                )
                if current_motion_index >= 0:
                    self.motion_combo.setCurrentIndex(
                        current_motion_index
                    )

                self.motion_strength_slider = QSlider(
                    Qt.Orientation.Horizontal
                )
                self.motion_strength_slider.setFocusPolicy(
                    Qt.FocusPolicy.NoFocus
                )
                self.motion_strength_slider.setRange(
                    0,
                    100,
                )
                self.motion_strength_slider.setValue(
                    int(
                        round(
                            outer.camera_motion_strength
                            * 100.0
                        )
                    )
                )
                self.motion_strength_slider.setMinimumWidth(
                    150
                )
                self.motion_strength_slider.setToolTip(
                    "How strongly the selected easing curve affects camera movement. "
                    "0% = linear; 100% = full easing."
                )

                self.motion_strength_label = QLabel()
                self.motion_strength_label.setMinimumWidth(
                    42
                )
                self.motion_strength_label.setAlignment(
                    Qt.AlignmentFlag.AlignRight
                    | Qt.AlignmentFlag.AlignVCenter
                )

                self.feedback_label = QLabel()
                self.feedback_label.setWordWrap(
                    True
                )
                self.feedback_label.setAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )
                self.feedback_label.setStyleSheet(
                    "color: palette(mid);"
                )

                # Trim values are separate compact chips rather than one
                # long sentence that forces the entire window wider.
                trim_values = compact_trim_labels(
                    outer.trim_start,
                    outer.trim_end,
                )
                self.trim_in_label = QLabel(
                    trim_values["in"]
                )
                self.trim_out_label = QLabel(
                    trim_values["out"]
                )
                self.trim_duration_label = QLabel(
                    trim_values["duration"]
                )

                chip_style = (
                    "QLabel {"
                    " padding: 3px 8px;"
                    " border: 1px solid palette(mid);"
                    " border-radius: 4px;"
                    "}"
                )

                for label in (
                    self.trim_in_label,
                    self.trim_out_label,
                    self.trim_duration_label,
                ):
                    label.setStyleSheet(
                        chip_style
                    )

                # ---------------------------------------------------------
                # Tool buttons: icons/tooltips avoid the long label row from
                # 0.18.0 while keeping actions discoverable.
                # ---------------------------------------------------------
                def tool_button(
                    icon,
                    tooltip,
                    *,
                    text=None,
                ):
                    button = QToolButton()
                    button.setFocusPolicy(
                        Qt.FocusPolicy.NoFocus
                    )
                    button.setToolTip(
                        tooltip
                    )
                    button.setAutoRaise(
                        False
                    )

                    if icon is not None:
                        button.setIcon(icon)

                    if text is not None:
                        button.setText(text)
                        button.setToolButtonStyle(
                            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
                            if icon is not None
                            else Qt.ToolButtonStyle.ToolButtonTextOnly
                        )

                    return button

                style = self.style()

                self.play_button = tool_button(
                    style.standardIcon(
                        QStyle.StandardPixmap.SP_MediaPlay
                    ),
                    "Play / Pause (Space)",
                )

                self.undo_button = tool_button(
                    style.standardIcon(
                        QStyle.StandardPixmap.SP_ArrowBack
                    ),
                    "Undo (Ctrl+Z)",
                )

                self.redo_button = tool_button(
                    style.standardIcon(
                        QStyle.StandardPixmap.SP_ArrowForward
                    ),
                    "Redo (Ctrl+Shift+Z or Ctrl+Y)",
                )

                self.save_button = tool_button(
                    style.standardIcon(
                        QStyle.StandardPixmap.SP_DialogSaveButton
                    ),
                    "Save project (Ctrl+S)",
                )

                self.delete_button = tool_button(
                    style.standardIcon(
                        QStyle.StandardPixmap.SP_TrashIcon
                    ),
                    "Delete Camera Position at current frame (Delete)",
                )

                self.use_view_button = QPushButton(
                    "Set Camera"
                )
                self.use_view_button.setFocusPolicy(
                    Qt.FocusPolicy.NoFocus
                )
                self.use_view_button.setToolTip(
                    "Set and save a Camera Position at this Source Time (Enter)"
                )
                self.use_view_button.setDefault(
                    True
                )

                self.in_button = QPushButton(
                    "Trim In"
                )
                self.out_button = QPushButton(
                    "Trim Out"
                )
                self.clear_trim_button = QToolButton()
                self.clear_trim_button.setText(
                    "Clear"
                )
                self.clear_trim_button.setToolTip(
                    "Clear Clip In/Out trim"
                )

                self.in_button.setToolTip(
                    "Set Clip trim In at the current Source Time (I)"
                )
                self.out_button.setToolTip(
                    "Set Clip trim Out at the current Source Time (O)"
                )
                self.clear_trim_button.setToolTip(
                    "Clear Clip trim and restore the full source range"
                )

                for button in (
                    self.in_button,
                    self.out_button,
                    self.clear_trim_button,
                ):
                    button.setFocusPolicy(
                        Qt.FocusPolicy.NoFocus
                    )

                self.play_button.clicked.connect(
                    self._toggle_playback
                )
                self.use_view_button.clicked.connect(
                    self._use_view
                )
                self.undo_button.clicked.connect(
                    self._undo_edit
                )
                self.redo_button.clicked.connect(
                    self._redo_edit
                )
                self.delete_button.clicked.connect(
                    self._delete_position
                )
                self.in_button.clicked.connect(
                    self._set_trim_in
                )
                self.out_button.clicked.connect(
                    self._set_trim_out
                )
                self.clear_trim_button.clicked.connect(
                    self._clear_trim
                )
                self.save_button.clicked.connect(
                    self._save_project
                )

                self.motion_combo.currentIndexChanged.connect(
                    self._motion_profile_changed
                )
                self.motion_strength_slider.valueChanged.connect(
                    self._motion_strength_preview
                )
                self.motion_strength_slider.sliderReleased.connect(
                    self._motion_strength_committed
                )

                # ---------------------------------------------------------
                # Timeline
                # ---------------------------------------------------------
                self.slider = TimeSlider(
                    Qt.Orientation.Horizontal
                )
                self.slider.setFocusPolicy(
                    Qt.FocusPolicy.NoFocus
                )

                duration_ms = int(
                    round(
                        max(
                            outer.source_duration or 0.0,
                            outer.source_time,
                        )
                        * 1000.0
                    )
                )
                self.slider.setRange(
                    0,
                    max(
                        1,
                        duration_ms,
                    ),
                )
                self.slider.setValue(
                    int(
                        round(
                            outer.source_time
                            * 1000.0
                        )
                    )
                )
                self.slider.sliderMoved.connect(
                    self._slider_moved
                )
                self.slider.sliderPressed.connect(
                    self._pause_playback
                )
                self.slider.sliderReleased.connect(
                    self._slider_released
                )

                # ---------------------------------------------------------
                # Layout
                #
                # Row 1: transport + authoritative time + save state
                # Row 2: edit operations + compact camera status
                # Row 3: trim chips
                # Row 4: timeline
                # ---------------------------------------------------------
                transport = QHBoxLayout()
                transport.setSpacing(6)
                transport.addWidget(
                    self.play_button
                )
                transport.addWidget(
                    self.use_view_button
                )
                transport.addSpacing(8)
                transport.addWidget(
                    self.time_label,
                    1,
                )
                transport.addWidget(
                    self.camera_position_label
                )
                transport.addWidget(
                    self.project_status_label
                )
                transport.addWidget(
                    self.undo_button
                )
                transport.addWidget(
                    self.redo_button
                )
                transport.addWidget(
                    self.save_button
                )

                edit_row = QHBoxLayout()
                edit_row.setSpacing(6)
                edit_row.addWidget(
                    self.in_button
                )
                edit_row.addWidget(
                    self.out_button
                )
                edit_row.addWidget(
                    self.clear_trim_button
                )
                edit_row.addWidget(
                    self.delete_button
                )
                edit_row.addSpacing(8)
                edit_row.addWidget(
                    self.clip_time_label
                )
                edit_row.addStretch(1)
                edit_row.addWidget(
                    self.camera_label
                )

                motion_row = QHBoxLayout()
                motion_row.setSpacing(6)

                motion_title = QLabel(
                    "Camera Motion"
                )
                motion_title.setStyleSheet(
                    "font-weight: 600;"
                )

                amount_title = QLabel(
                    "Amount"
                )

                motion_row.addWidget(
                    motion_title
                )
                motion_row.addWidget(
                    self.motion_combo
                )
                motion_row.addSpacing(10)
                motion_row.addWidget(
                    amount_title
                )
                motion_row.addWidget(
                    self.motion_strength_slider,
                    1,
                )
                motion_row.addWidget(
                    self.motion_strength_label
                )

                trim_row = QHBoxLayout()
                trim_row.setSpacing(6)
                trim_row.addStretch(1)
                trim_row.addWidget(
                    self.trim_in_label
                )
                trim_row.addWidget(
                    self.trim_duration_label
                )
                trim_row.addWidget(
                    self.trim_out_label
                )
                trim_row.addStretch(1)

                controls_frame = QFrame()
                controls_frame.setFrameShape(
                    QFrame.Shape.StyledPanel
                )

                controls_layout = QVBoxLayout(
                    controls_frame
                )
                controls_layout.setContentsMargins(
                    8,
                    7,
                    8,
                    7,
                )
                controls_layout.setSpacing(5)
                controls_layout.addLayout(
                    transport
                )
                controls_layout.addLayout(
                    edit_row
                )
                controls_layout.addLayout(
                    motion_row
                )
                controls_layout.addWidget(
                    self.feedback_label
                )
                controls_layout.addLayout(
                    trim_row
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
                layout.setSpacing(8)
                layout.addWidget(
                    self.canvas,
                    1,
                )
                layout.addWidget(
                    controls_frame,
                    0,
                )

                # Keep the initial editor compact. Long labels no longer drive
                # the top-level window size.
                minimum_width = max(
                    760,
                    int(
                        self.image_label.minimumSizeHint().width()
                    ),
                )
                self.resize(
                    max(
                        860,
                        outer.landscape_size[0] + 32,
                    ),
                    outer.landscape_size[1] + 190,
                )
                self.setMinimumWidth(
                    minimum_width
                )

                self.image_label.mousePressEvent = (
                    self._image_mouse_press
                )
                self.image_label.mouseReleaseEvent = (
                    self._image_mouse_release
                )
                self.image_label.mouseMoveEvent = (
                    self._image_mouse_move
                )
                self.image_label.wheelEvent = (
                    self._image_wheel
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
                                / outer.playback_fps
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
                value = (
                    outer.source_time
                    if preview_time is None
                    else float(preview_time)
                )

                self.time_label.setText(
                    f"{format_time(value)}  /  {self._duration_text()}"
                )

                local = (
                    value
                    - outer.trim_start
                )

                local_text = (
                    format_time(
                        max(
                            0.0,
                            local,
                        )
                    )
                    if outer.source_time_inside_trim(
                        value
                    )
                    else "outside clip"
                )

                self.clip_time_label.setText(
                    f"Clip {local_text} / {format_time(outer.clip_duration)}"
                )

            def _update_trim_status(self):
                values = compact_trim_labels(
                    outer.trim_start,
                    outer.trim_end,
                )

                self.trim_in_label.setText(
                    values["in"]
                )
                self.trim_out_label.setText(
                    values["out"]
                )
                self.trim_duration_label.setText(
                    values["duration"]
                )

                feedback = (
                    outer.last_edit_message
                    if outer.last_edit_message
                    and (
                        outer.last_edit_message.startswith(
                            "Camera Position"
                        )
                        or outer.last_edit_message.startswith(
                            "Camera motion"
                        )
                        or outer.last_edit_message.startswith(
                            "Clip In set:"
                        )
                        or outer.last_edit_message.startswith(
                            "Clip Out set:"
                        )
                        or outer.last_edit_message.startswith(
                            "Clip trim cleared"
                        )
                        or outer.last_edit_message.startswith(
                            "No Camera Position"
                        )
                    )
                    else (
                        "Preview-only camera — Set Camera to save this view"
                        if outer.can_preview_transient_hold
                        else ""
                    )
                )

                self.feedback_label.setText(
                    feedback
                )
                self.feedback_label.setVisible(
                    bool(
                        feedback
                    )
                )

            def _refresh_edit_controls(self):
                self.undo_button.setEnabled(
                    outer.can_undo
                )
                self.redo_button.setEnabled(
                    outer.can_redo
                )
                self.save_button.setEnabled(
                    outer.project_dirty
                )

                self.undo_button.setToolTip(
                    (
                        f"Undo {outer.undo_label} (Ctrl+Z)"
                        if outer.undo_label
                        else "Undo (Ctrl+Z)"
                    )
                )
                self.redo_button.setToolTip(
                    (
                        f"Redo {outer.redo_label} (Ctrl+Shift+Z or Ctrl+Y)"
                        if outer.redo_label
                        else "Redo (Ctrl+Shift+Z or Ctrl+Y)"
                    )
                )

                self.project_status_label.setText(
                    "Modified"
                    if outer.project_dirty
                    else "Saved"
                )

                self.camera_position_label.setText(
                    f"CAM {outer.camera_position_count}"
                )

                self.camera_label.setText(
                    compact_camera_text(
                        outer.state.yaw_deg,
                        outer.state.pitch_deg,
                        outer.state.fov_deg,
                        outer.state.aspect,
                    )
                )

                motion_index = self.motion_combo.findData(
                    outer.camera_motion_easing
                )
                if (
                    motion_index >= 0
                    and motion_index
                    != self.motion_combo.currentIndex()
                ):
                    self.motion_combo.blockSignals(
                        True
                    )
                    self.motion_combo.setCurrentIndex(
                        motion_index
                    )
                    self.motion_combo.blockSignals(
                        False
                    )

                strength_value = int(
                    round(
                        outer.camera_motion_strength
                        * 100.0
                    )
                )
                if (
                    self.motion_strength_slider.value()
                    != strength_value
                ):
                    self.motion_strength_slider.blockSignals(
                        True
                    )
                    self.motion_strength_slider.setValue(
                        strength_value
                    )
                    self.motion_strength_slider.blockSignals(
                        False
                    )
                self.motion_strength_label.setText(
                    f"{strength_value}%"
                )

                suffix = (
                    " *"
                    if outer.project_dirty
                    else ""
                )
                self.setWindowTitle(
                    WINDOW_TITLE
                    + suffix
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
                self.image_label.setPixmap(
                    QPixmap.fromImage(
                        image
                    )
                )
                self.image_label.setFixedSize(
                    width,
                    height,
                )
                self.slider.setValue(
                    int(
                        round(
                            outer.source_time
                            * 1000.0
                        )
                    )
                )
                self._update_time_label()
                self._update_trim_status()
                self._refresh_edit_controls()
                self.slider.update()
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

            def _use_view(self):
                self._pause_playback()

                try:
                    outer.use_this_view()
                except Exception as exc:
                    QMessageBox.critical(
                        self,
                        "PanoPilot — Camera Position failed",
                        str(exc),
                    )
                    self._refresh()
                    return False

                self._refresh()
                return True

            def _motion_strength_preview(
                self,
                value,
            ):
                self.motion_strength_label.setText(
                    f"{int(value)}%"
                )

            def _apply_motion_settings(self):
                easing = self.motion_combo.currentData()
                strength = (
                    self.motion_strength_slider.value()
                    / 100.0
                )

                try:
                    outer.set_camera_motion(
                        easing=easing,
                        strength=strength,
                    )
                except Exception as exc:
                    QMessageBox.critical(
                        self,
                        "PanoPilot — Camera Motion failed",
                        str(exc),
                    )
                    return False

                self._refresh()
                return True

            def _motion_profile_changed(
                self,
                _index,
            ):
                self._apply_motion_settings()

            def _motion_strength_committed(
                self,
            ):
                self._apply_motion_settings()

            def _save_project(self):
                self._pause_playback()
                try:
                    outer.save_project()
                except Exception as exc:
                    QMessageBox.critical(
                        self,
                        "PanoPilot — Save failed",
                        str(exc),
                    )
                    return False
                self._refresh()
                return True

            def _undo_edit(self):
                self._pause_playback()
                outer.undo_edit()
                self._refresh()

            def _redo_edit(self):
                self._pause_playback()
                outer.redo_edit()
                self._refresh()

            def _delete_position(self):
                self._pause_playback()
                outer.delete_current_position()
                self._refresh()

            def _run_trim_edit(self, operation):
                self._pause_playback()
                try:
                    operation()
                except ValueError as exc:
                    QMessageBox.warning(
                        self, "PanoPilot — Invalid trim", str(exc)
                    )
                    return False
                self._refresh()
                return True

            def _set_trim_in(self):
                return self._run_trim_edit(outer.set_trim_in_here)

            def _set_trim_out(self):
                return self._run_trim_edit(outer.set_trim_out_here)

            def _clear_trim(self):
                return self._run_trim_edit(outer.clear_trim)

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

                start_time = outer.playback_start_time()
                outer.begin_playback_view()

                # With a persisted View Path, playback restores/evaluates that
                # path. With zero Camera Positions and a manually explored
                # camera, playback preserves the transient camera as a
                # preview-only hold.
                outer.seek_for_playback(
                    start_time
                )
                outer.at_playback_end = False
                self._refresh()
                outer.playing = True
                self.play_button.setIcon(
                    self.style().standardIcon(
                        QStyle.StandardPixmap.SP_MediaPause
                    )
                )
                self.play_button.setToolTip(
                    "Pause (Space)"
                )
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

                # Keep the currently displayed transient camera after Pause,
                # but clear the playback-mode bookkeeping. A subsequent Play
                # will detect it again as an explored, unsaved view.
                outer.end_playback_view()
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
                if target >= outer.trim_end:
                    self._seek_to(outer.trim_end)
                    self._pause_playback()
                    return
                try:
                    outer.seek_for_playback(
                        target
                    )
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
                modifiers = event.modifiers()
                control = bool(
                    modifiers & Qt.KeyboardModifier.ControlModifier
                )
                shift = bool(
                    modifiers & Qt.KeyboardModifier.ShiftModifier
                )

                if control and key == Qt.Key.Key_S:
                    self._save_project()
                    return

                if control and key == Qt.Key.Key_Z:
                    if shift:
                        self._redo_edit()
                    else:
                        self._undo_edit()
                    return

                if control and key == Qt.Key.Key_Y:
                    self._redo_edit()
                    return

                if key in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
                    self._pause_playback()
                    self.close()
                    return

                if key == Qt.Key.Key_Space:
                    self._toggle_playback()
                    return

                if key in (
                    Qt.Key.Key_Return,
                    Qt.Key.Key_Enter,
                ):
                    self._use_view()
                    return

                if key in (
                    Qt.Key.Key_Delete,
                    Qt.Key.Key_Backspace,
                ):
                    self._delete_position()
                    return

                if key == Qt.Key.Key_I:
                    self._set_trim_in()
                    return

                if key == Qt.Key.Key_O:
                    self._set_trim_out()
                    return

                if key == Qt.Key.Key_Left:
                    self._pause_playback()
                    self._seek_to(
                        outer.source_time
                        - outer.seek_step_seconds
                    )
                    return

                if key == Qt.Key.Key_Right:
                    self._pause_playback()
                    self._seek_to(
                        outer.source_time
                        + outer.seek_step_seconds
                    )
                    return

                if key == Qt.Key.Key_R:
                    self._pause_playback()
                    outer.state.reset()
                    self._refresh()
                    return

                if key == Qt.Key.Key_1:
                    self._pause_playback()
                    outer.set_output_aspect("16:9")
                    self._refresh()
                    return

                if key == Qt.Key.Key_2:
                    self._pause_playback()
                    outer.set_output_aspect("9:16")
                    self._refresh()
                    return

                if key == Qt.Key.Key_H:
                    outer.show_hud = not outer.show_hud
                    self._refresh()
                    return

                super().keyPressEvent(event)

            def closeEvent(self, event):
                self._pause_playback()

                if outer.project_dirty:
                    box = QMessageBox(self)
                    box.setWindowTitle("PanoPilot — Unsaved changes")
                    box.setText(
                        "Save changes to the PanoPilot project before closing?"
                    )
                    box.setInformativeText(
                        "Save writes the project atomically. "
                        "Discard leaves the existing project file unchanged."
                    )
                    box.setStandardButtons(
                        QMessageBox.StandardButton.Save
                        | QMessageBox.StandardButton.Discard
                        | QMessageBox.StandardButton.Cancel
                    )
                    box.setDefaultButton(
                        QMessageBox.StandardButton.Save
                    )

                    choice = box.exec()

                    if choice == QMessageBox.StandardButton.Save:
                        if not self._save_project():
                            event.ignore()
                            return
                    elif choice == QMessageBox.StandardButton.Discard:
                        outer.discard_unsaved()
                    else:
                        event.ignore()
                        return

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

        widget = EditorWidget()
        widget.show()
        widget.raise_()
        widget.activateWindow()
        widget.setFocus()

        # Normal Qt event dispatch is required by QMediaPlayer, precise timers,
        # queued worker signals, and Wayland window transitions. Do not poll
        # QApplication.processEvents() in a Python loop.
        window_loop.exec()

        return {
            "source_time": float(self.source_time),
            "source_duration": self.source_duration,
            "yaw_deg": float(self.state.yaw_deg),
            "pitch_deg": float(self.state.pitch_deg),
            "fov_deg": float(self.state.fov_deg),
            "aspect": self.state.aspect,
            "camera_position_markers": list(self.marker_times),
            "dormant_camera_position_markers": list(self.dormant_marker_times),
            "camera_position_count": int(
                len(self.marker_times)
                + len(self.dormant_marker_times)
            ),
            "camera_motion": {
                "easing": self.camera_motion_easing,
                "strength": float(
                    self.camera_motion_strength
                ),
            },
            "trim_in_source_time": float(self.trim_start),
            "trim_out_source_time": (
                float(self.trim_out_source_time)
                if self.trim_out_source_time is not None
                else None
            ),
            "resolved_trim_out_source_time": float(self.trim_end),
            "clip_duration": float(self.clip_duration),
            "clip_local_time": float(self.clip_local_time()),
            "playback_fps": float(self.playback_fps),
            "playback_view_mode": str(
                self.playback_view_mode
            ),
            "audio_clock": self.audio_clock,
            "at_playback_end": bool(self.at_playback_end),
            "last_render_ms": (
                float(self.last_render_seconds * 1000.0)
                if self.last_render_seconds is not None else None
            ),
            "last_seek_ms": (
                float(self.last_seek_seconds * 1000.0)
                if self.last_seek_seconds is not None else None
            ),
            "last_commit": self.last_commit,
            "camera_exploration_changed": bool(
                self.camera_exploration_changed
            ),
            "project_dirty": bool(self.project_dirty),
            "can_undo": bool(self.can_undo),
            "can_redo": bool(self.can_redo),
            "undo_label": self.undo_label,
            "redo_label": self.redo_label,
            "saved_this_session": bool(self.saved_this_session),
            "ui_backend": "PySide6/Qt",
        }


def explore_osv(
    source,
    *,
    source_time=None,
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
    clip_id=None,
):
    view_long_edge = int(view_long_edge)
    if view_long_edge < 320:
        raise ValueError("view_long_edge must be at least 320")

    loaded_project = load_project(
        project_path,
        default_aspect=aspect,
    )
    session = ProjectSession(
        loaded_project,
        path=project_path,
    )
    if clip_id is not None:
        existing_clip = (
            session.project.clip_for_id(
                str(clip_id)
            )
        )

        if existing_clip is None:
            raise ValueError(
                f"Project has no Clip id {clip_id!r}"
            )

        if str(existing_clip.source) != str(source):
            raise ValueError(
                "Selected Clip source mismatch: "
                f"{existing_clip.source!r} != {source!r}"
            )

        active_clip_id = (
            existing_clip.id
        )
    else:
        existing_clip = (
            session.project.clip_for_source(
                str(source),
                create=False,
            )
        )
        active_clip_id = (
            existing_clip.id
            if existing_clip is not None
            else None
        )

    if source_time is None:
        source_time = (
            float(existing_clip.trim_in_source_time)
            if existing_clip is not None
            else 0.0
        )
    else:
        source_time = float(source_time)

    path_sample = (
        evaluate_clip_view_path(
            existing_clip,
            source_time,
            interpolation=session.project.camera_motion_easing,
            strength=session.project.camera_motion_strength,
        )
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
    initial_aspect = (
        session.project.output_aspect
        if session.project.clips
        else aspect
    )

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

        def prepare_cache(progress):
            def cache_progress(event):
                message = str(
                    event.get(
                        "message",
                        "Preparing panoramic preview",
                    )
                )
                progress(message)

            return ensure_preview_cache(
                source,
                profile=profile,
                cache_dir=cache_dir,
                rebuild=rebuild_preview,
                progress_callback=cache_progress,
            )

        cache_entry = run_with_loading_screen(
            prepare_cache,
            title="PanoPilot",
            message="Preparing panoramic view",
            detail=Path(source).name,
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
        def prepare_single_frame(progress):
            progress(
                f"Preparing Source Time {float(source_time):.3f}s"
            )
            return render_osv_panorama_frame(
                source,
                source_time=source_time,
                width=panorama_width,
                height=panorama_height,
                level_horizon=level_horizon,
                level_strength=level_strength,
                imu_source=imu_source,
                imu_offset_ms=imu_offset_ms,
            )

        panorama, initial_diagnostics = run_with_loading_screen(
            prepare_single_frame,
            title="PanoPilot",
            message="Preparing panoramic view",
            detail=Path(source).name,
        )
        source_duration = initial_diagnostics.get(
            "source_duration"
        )
        preview_fps = 1.0

    # The cache represents discrete editing frames.  If the requested time
    # snapped to a nearby cache frame, evaluate the persisted View Path at the
    # exact frame the user is actually seeing.
    path_sample = (
        evaluate_clip_view_path(
            existing_clip,
            source_time,
            interpolation=session.project.camera_motion_easing,
            strength=session.project.camera_motion_strength,
        )
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
        if active_clip_id is not None:
            return session.project.clip_for_id(
                active_clip_id
            )

        return session.project.clip_for_source(
            str(source),
            create=False,
        )

    def marker_times():
        clip = current_clip()
        return [] if clip is None else [
            float(position.source_time)
            for position in clip.active_camera_positions()
        ]

    def dormant_marker_times():
        clip = current_clip()
        return [] if clip is None else [
            float(position.source_time)
            for position in clip.dormant_camera_positions()
        ]

    def trim_state():
        clip = current_clip()
        return {
            "trim_in_source_time": (
                float(clip.trim_in_source_time) if clip is not None else 0.0
            ),
            "trim_out_source_time": (
                float(clip.trim_out_source_time)
                if clip is not None and clip.trim_out_source_time is not None
                else None
            ),
        }

    def persisted_camera_at(target_time):
        clip = current_clip()

        if clip is None:
            return VirtualCamera(
                0.0,
                0.0,
                90.0,
            )

        return evaluate_clip_view_path(
            clip,
            target_time,
            interpolation=session.project.camera_motion_easing,
            strength=session.project.camera_motion_strength,
        ).camera

    def session_payload(
        transaction=None,
        *,
        source_time=None,
        include_camera=False,
    ):
        payload = {
            **session.state(),
            "project_path": str(project_path),
            "marker_times": marker_times(),
            "dormant_marker_times": dormant_marker_times(),
            "aspect": session.project.output_aspect,
            "camera_motion_easing": (
                session.project.camera_motion_easing
            ),
            "camera_motion_strength": float(
                session.project.camera_motion_strength
            ),
            **trim_state(),
        }

        if transaction is not None:
            payload.update(transaction)

        if include_camera and source_time is not None:
            payload["camera"] = persisted_camera_at(
                source_time
            )

        return payload

    def commit_callback(
        *,
        source_time,
        yaw_deg,
        pitch_deg,
        fov_deg,
        aspect,
    ):
        if active_clip_id is not None:
            transaction = (
                session.commit_camera_position_to_clip(
                    active_clip_id,
                    source_time=source_time,
                    yaw_deg=yaw_deg,
                    pitch_deg=pitch_deg,
                    fov_deg=fov_deg,
                    output_aspect=aspect,
                )
            )
        else:
            transaction = session.commit_camera_position(
                source,
                source_time=source_time,
                yaw_deg=yaw_deg,
                pitch_deg=pitch_deg,
                fov_deg=fov_deg,
                output_aspect=aspect,
            )

        operation = transaction.get("result") or {}

        return session_payload(
            {
                **transaction,
                **operation,
            },
            source_time=source_time,
        )

    def save_callback():
        result = session.save(project_path)
        return session_payload(result)

    def undo_callback(*, source_time):
        transaction = session.undo()
        return session_payload(
            transaction,
            source_time=source_time,
            include_camera=True,
        )

    def redo_callback(*, source_time):
        transaction = session.redo()
        return session_payload(
            transaction,
            source_time=source_time,
            include_camera=True,
        )

    def delete_callback(*, source_time):
        frame_tolerance = max(
            0.001,
            0.51 / float(
                cache_reader.fps
                if cache_reader is not None
                else max(preview_fps, 1.0)
            ),
        )

        if active_clip_id is not None:
            transaction = (
                session.delete_camera_position_from_clip(
                    active_clip_id,
                    source_time=source_time,
                    tolerance_s=frame_tolerance,
                )
            )
        else:
            transaction = session.delete_camera_position(
                source,
                source_time=source_time,
                tolerance_s=frame_tolerance,
            )

        return session_payload(
            transaction,
            source_time=source_time,
            include_camera=True,
        )

    def aspect_callback(*, aspect, source_time):
        transaction = session.set_output_aspect(
            aspect
        )
        return session_payload(
            transaction,
            source_time=source_time,
        )

    def motion_callback(
        *,
        easing,
        strength,
        source_time,
    ):
        transaction = session.set_camera_motion(
            easing=easing,
            strength=strength,
        )

        return session_payload(
            transaction,
            source_time=source_time,
            include_camera=True,
        )

    def discard_callback(*, source_time):
        transaction = session.discard_to_saved()
        return session_payload(
            transaction,
            source_time=source_time,
            include_camera=True,
        )

    def set_trim_in_callback(*, source_time):
        frame_duration = 1.0 / float(
            cache_reader.fps
            if cache_reader is not None
            else max(preview_fps, 1.0)
        )
        if active_clip_id is not None:
            transaction = (
                session.set_clip_trim_in_by_id(
                    active_clip_id,
                    source_time=source_time,
                    source_duration=source_duration,
                    min_duration_s=frame_duration,
                )
            )
        else:
            transaction = session.set_clip_trim_in(
                source,
                source_time=source_time,
                source_duration=source_duration,
                min_duration_s=frame_duration,
            )
        return session_payload(
            transaction, source_time=source_time, include_camera=True
        )

    def set_trim_out_callback(*, source_time):
        frame_duration = 1.0 / float(
            cache_reader.fps
            if cache_reader is not None
            else max(preview_fps, 1.0)
        )
        if active_clip_id is not None:
            transaction = (
                session.set_clip_trim_out_by_id(
                    active_clip_id,
                    source_time=source_time,
                    source_duration=source_duration,
                    min_duration_s=frame_duration,
                )
            )
        else:
            transaction = session.set_clip_trim_out(
                source,
                source_time=source_time,
                source_duration=source_duration,
                min_duration_s=frame_duration,
            )
        return session_payload(
            transaction, source_time=source_time, include_camera=True
        )

    def clear_trim_callback(*, source_time):
        transaction = (
            session.clear_clip_trim_by_id(
                active_clip_id
            )
            if active_clip_id is not None
            else session.clear_clip_trim(
                source
            )
        )
        return session_payload(
            transaction, source_time=source_time, include_camera=True
        )

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
            sample = evaluate_clip_view_path(
                clip,
                target_time,
                interpolation=session.project.camera_motion_easing,
                strength=session.project.camera_motion_strength,
            )
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
            "aspect": session.project.output_aspect,
            "marker_times": marker_times(),
            "dormant_marker_times": dormant_marker_times(),
            **trim_state(),
            "diagnostics": diagnostics,
        }

    window = ExploreWindow(
        panorama,
        state=state,
        source_time=source_time,
        source_duration=source_duration,
        commit_callback=commit_callback,
        seek_callback=seek_callback,
        save_callback=save_callback,
        undo_callback=undo_callback,
        redo_callback=redo_callback,
        delete_callback=delete_callback,
        aspect_callback=aspect_callback,
        discard_callback=discard_callback,
        trim_in_callback=set_trim_in_callback,
        trim_out_callback=set_trim_out_callback,
        clear_trim_callback=clear_trim_callback,
        motion_callback=motion_callback,
        marker_times=marker_times(),
        dormant_marker_times=dormant_marker_times(),
        trim_in_source_time=trim_state()["trim_in_source_time"],
        trim_out_source_time=trim_state()["trim_out_source_time"],
        camera_motion_easing=(
            session.project.camera_motion_easing
        ),
        camera_motion_strength=(
            session.project.camera_motion_strength
        ),
        seek_step_seconds=seek_step_seconds,
        playback_fps=(cache_reader.fps if cache_reader is not None else preview_fps),
        cache_media_path=(cache_entry.video_path if cache_entry is not None else None),
        audio_enabled=(audio_enabled and cache_entry is not None),
        landscape_size=landscape_size,
        portrait_size=portrait_size,
        show_hud=show_hud,
    )

    window._apply_project_state(
        session_payload()
    )

    try:
        final_state = window.run()
    finally:
        if cache_reader is not None:
            cache_reader.close()

    clip = current_clip()
    return {
        "source": str(source),
        "clip_id": (
            active_clip_id
            if active_clip_id is not None
            else (
                clip.id
                if clip is not None
                else None
            )
        ),
        "source_time": float(final_state["source_time"]),
        "project_path": str(project_path),
        "project_exists": Path(project_path).exists(),
        "initial_view_path": path_sample.to_dict() if path_sample is not None else None,
        "camera_position_count": len(clip.camera_positions) if clip is not None else 0,
        "project_dirty": bool(session.dirty),
        "history": session.state(),
        "preview_cache": cache_entry.to_dict() if cache_entry is not None else None,
        "panorama": initial_diagnostics,
        "explore_state": final_state,
    }
