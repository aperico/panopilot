"""
Interactive PanoPilot desktop editor.

0.15 moves editing onto a disposable panoramic preview cache and adds real-time
playback.  The original OSV remains immutable and authoritative for final
rendering.

Editing invariant (0.50):

    seek / play                         = navigation
    Enter / Return                      = create Camera Position at playhead
    drag / wheel / fine camera controls = update closest Camera Position left
                                          when one exists

A continuous direct-manipulation gesture remains one logical edit transaction.

Space is now the conventional Play/Pause shortcut.

0.40 extends the precise View Direction controls with explicit clockwise and
counter-clockwise roll rotation so all three camera orientation axes can be
adjusted without relying on mouse gestures.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import sys
import time

import cv2

from .branding import application_icon_path, set_application_icon
from .desktop_theme import WORKSPACE_STYLESHEET
from .thumbnails import filmstrip_tile_geometry, sample_video_thumbnails_range
from .cache import (
    PanoramaCacheReader,
    PreviewProfile,
    ensure_preview_cache,
)
from .pipeline import render_osv_panorama_frame
from .loading import run_with_loading_screen
from .project import assert_project_sources, load_project
from .session import ProjectSession
from .virtual_camera import VirtualCamera, reframe_equirectangular
from .view_path import evaluate_clip_view_path
from .timeline_navigation import TimelineViewport


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


def compact_camera_text(
    yaw_deg,
    pitch_deg,
    fov_deg,
    aspect,
    roll_deg=0.0,
):
    return (
        f"Yaw {float(yaw_deg):+.1f}°   "
        f"Pitch {float(pitch_deg):+.1f}°   "
        f"Roll {float(roll_deg):+.1f}°   "
        f"FOV {float(fov_deg):.1f}°   "
        f"{aspect}"
    )


@dataclass
class ExploreState:
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    fov_deg: float = 90.0
    aspect: str = "16:9"

    initial_yaw_deg: float = 0.0
    initial_pitch_deg: float = 0.0
    initial_roll_deg: float = 0.0
    initial_fov_deg: float = 90.0
    initial_aspect: str = "16:9"

    pitch_limit_deg: float = 85.0
    min_fov_deg: float = 30.0
    max_fov_deg: float = 120.0

    def __post_init__(self):
        self._validate_aspect(self.aspect)
        self._validate_aspect(self.initial_aspect)
        self.yaw_deg = self._wrap_yaw(self.yaw_deg)
        self.roll_deg = self._wrap_yaw(
            self.roll_deg
        )
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
            roll_deg=self.roll_deg,
        )

    def snapshot(self):
        return (
            float(self.yaw_deg),
            float(self.pitch_deg),
            float(self.fov_deg),
            str(self.aspect),
            float(self.roll_deg),
        )

    def set_camera(self, camera, *, aspect=None, make_initial=False):
        self.yaw_deg = self._wrap_yaw(camera.yaw_deg)
        self.pitch_deg = self._clamp_pitch(camera.pitch_deg)
        self.roll_deg = self._wrap_yaw(
            getattr(
                camera,
                "roll_deg",
                0.0,
            )
        )
        self.fov_deg = self._clamp_fov(camera.fov_deg)

        if aspect is not None:
            self._validate_aspect(aspect)
            self.aspect = aspect

        if make_initial:
            self.initial_yaw_deg = self.yaw_deg
            self.initial_pitch_deg = self.pitch_deg
            self.initial_roll_deg = self.roll_deg
            self.initial_fov_deg = self.fov_deg
            self.initial_aspect = self.aspect

    def reset(self):
        self.yaw_deg = self._wrap_yaw(self.initial_yaw_deg)
        self.pitch_deg = self._clamp_pitch(self.initial_pitch_deg)
        self.roll_deg = self._wrap_yaw(
            self.initial_roll_deg
        )
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

    def nudge_view(
        self,
        *,
        yaw_delta_deg=0.0,
        pitch_delta_deg=0.0,
        roll_delta_deg=0.0,
    ):
        """Precisely nudge the transient Virtual Camera orientation.

        Positive yaw looks right. Positive pitch looks up. Positive roll rotates the view clockwise. This is an
        transient camera operation. The desktop Reframe presenter decides when
        the resulting state is committed to the active Camera Position.
        """
        self.yaw_deg = self._wrap_yaw(
            self.yaw_deg
            + float(
                yaw_delta_deg
            )
        )
        self.pitch_deg = self._clamp_pitch(
            self.pitch_deg
            + float(
                pitch_delta_deg
            )
        )
        self.roll_deg = self._wrap_yaw(
            self.roll_deg
            + float(
                roll_delta_deg
            )
        )

        return self.camera()

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
        move_position_callback=None,
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
        initial_mode="reframe",
        arrange_callback=None,
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
        self.move_position_callback = move_position_callback
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
        self.initial_mode = str(initial_mode) if str(initial_mode) in ("reframe", "trim") else "reframe"
        self.arrange_callback = arrange_callback
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

    @staticmethod
    def monotonic_playback_target(anchor_source, anchor_wall, *, now=None):
        """Return authoritative editor playback time from a monotonic clock.

        Qt Multimedia remains responsible for audio output, but visual playback
        must never stop because the media player's reported position stalls.
        """
        current = time.perf_counter() if now is None else float(now)
        return max(0.0, float(anchor_source) + max(0.0, current - float(anchor_wall)))

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
            float(
                self.state.initial_roll_deg
            ),
        )

        numeric_delta = max(
            abs(current[0] - initial[0]),
            abs(current[1] - initial[1]),
            abs(current[2] - initial[2]),
            abs(current[4] - initial[4]),
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
            abs(current[4] - saved[4]),
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

    def move_camera_position(self, source_time, new_source_time):
        if self.move_position_callback is None:
            raise RuntimeError("No Camera Position move callback was configured")
        result = self.move_position_callback(
            source_time=float(source_time),
            new_source_time=float(new_source_time),
        )
        self._apply_project_state(result, restore_camera=True)
        self.last_commit = None
        operation = result.get("result") or {}
        if operation.get("moved"):
            self.last_edit_message = (
                "Camera Position moved: "
                f"{float(operation['previous_source_time']):.3f}s → "
                f"{float(operation['source_time']):.3f}s"
            )
            if result.get("changed") and self.save_callback is not None:
                save_result = self.save_callback()
                self._apply_project_state(save_result)
                self.saved_this_session = bool(save_result.get("saved"))
        else:
            self.last_edit_message = "Camera Position was not moved"
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

    def camera_position_anchor_time(self, source_time=None):
        """Return the closest saved Camera Position at or left of Source Time.

        Reframing is segment-oriented: once a Camera Position exists, changing
        the view anywhere to its right edits that left-hand position until the
        next diamond is crossed.  This keeps the visible timeline marker as the
        authoritative edit target and avoids creating accidental keyframes.
        """
        value = self.source_time if source_time is None else float(source_time)
        markers = sorted(set(self.marker_times) | set(self.dormant_marker_times))
        candidates = [marker for marker in markers if marker <= value + 1e-6]
        return None if not candidates else float(candidates[-1])

    def _commit_view_at(self, source_time, *, automatic=False):
        if self.commit_callback is None:
            raise RuntimeError(
                "No Camera Position persistence callback was configured"
            )

        self.end_playback_view()
        anchor_time = self._clamp_time(source_time)
        result = self.commit_callback(
            source_time=anchor_time,
            yaw_deg=self.state.yaw_deg,
            pitch_deg=self.state.pitch_deg,
            fov_deg=self.state.fov_deg,
            roll_deg=self.state.roll_deg,
            aspect=self.state.aspect,
        )

        self.last_commit = result
        self.last_committed_snapshot = self.state.snapshot()
        # Do not restore the persisted camera here. For an automatic update the
        # playhead may be to the right of the Camera Position; the User should
        # continue seeing the view they just manipulated at the current frame.
        self._apply_project_state(result)

        autosaved = False
        if result.get("changed") and self.save_callback is not None:
            save_result = self.save_callback()
            self._apply_project_state(save_result)
            self.saved_this_session = bool(save_result.get("saved"))
            autosaved = self.saved_this_session

        position_number = result.get("position_number")
        if position_number is not None:
            action = "created" if result.get("created") else "updated"
            persistence = "saved" if autosaved else "set"
            automatic_text = " automatically" if automatic else ""
            self.last_edit_message = (
                f"Camera Position {int(position_number):02d} "
                f"{action} and {persistence}{automatic_text} @ {format_time(anchor_time)}"
            )

        return {**result, "autosaved": bool(autosaved), "anchor_time": anchor_time}

    def use_this_view(self):
        """Create/update a Camera Position at the current Source Time."""
        return self._commit_view_at(self.source_time, automatic=False)

    def update_left_camera_position(self):
        """Persist the current view into the closest Camera Position to the left.

        Returns a no-op result when there is no left-hand Camera Position. The
        explicit Add / Update action remains the way to create the first marker.
        """
        anchor = self.camera_position_anchor_time()
        if anchor is None:
            self.last_edit_message = (
                "No Camera Position to the left — add one before reframing"
            )
            return {
                "changed": False,
                "reason": "no-camera-position-to-left",
                "anchor_time": None,
            }
        return self._commit_view_at(anchor, automatic=True)

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
                "add a Camera Position to persist"
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
            anchor = self.camera_position_anchor_time()
            if anchor is None:
                status = (
                    "REFRAME — add a Camera Position; view changes before the first "
                    "diamond remain preview-only"
                )
            else:
                status = (
                    "REFRAME — view edits auto-save to Camera Position @ "
                    f"{format_time(anchor)}"
                )

        lines = [
            status,
            compact_camera_text(
                self.state.yaw_deg,
                self.state.pitch_deg,
                self.state.fov_deg,
                self.state.aspect,
                roll_deg=self.state.roll_deg,
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

    def result_state(self):
        """Return the GUI-independent editor state snapshot.

        Keeping result construction outside the Qt event-loop plumbing allows
        embedded workspaces to close asynchronously without changing the
        established single-Clip ``explore_osv`` result contract.
        """
        return {
            "source_time": float(self.source_time),
            "source_duration": self.source_duration,
            "yaw_deg": float(self.state.yaw_deg),
            "pitch_deg": float(self.state.pitch_deg),
            "roll_deg": float(self.state.roll_deg),
            "fov_deg": float(self.state.fov_deg),
            "aspect": self.state.aspect,
            "camera_position_markers": list(self.marker_times),
            "dormant_camera_position_markers": list(self.dormant_marker_times),
            "camera_position_count": int(len(self.marker_times) + len(self.dormant_marker_times)),
            "camera_motion": {
                "easing": self.camera_motion_easing,
                "strength": float(self.camera_motion_strength),
            },
            "trim_in_source_time": float(self.trim_start),
            "trim_out_source_time": (
                float(self.trim_out_source_time)
                if self.trim_out_source_time is not None else None
            ),
            "resolved_trim_out_source_time": float(self.trim_end),
            "clip_duration": float(self.clip_duration),
            "clip_local_time": float(self.clip_local_time()),
            "playback_fps": float(self.playback_fps),
            "playback_view_mode": str(self.playback_view_mode),
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
            "camera_exploration_changed": bool(self.camera_exploration_changed),
            "project_dirty": bool(self.project_dirty),
            "can_undo": bool(self.can_undo),
            "can_redo": bool(self.can_redo),
            "undo_label": self.undo_label,
            "redo_label": self.redo_label,
            "saved_this_session": bool(self.saved_this_session),
            "ui_backend": "PySide6/Qt",
        }

    def run(self, *, embed_host=None, on_closed=None):
        try:
            from PySide6.QtCore import QEvent, QEventLoop, QPointF, QTimer, QUrl, Qt
            from PySide6.QtGui import (
                QColor, QIcon, QImage, QKeyEvent, QMouseEvent,
                QPainter, QPen, QPixmap, QPolygonF, QWheelEvent,
            )
            from PySide6.QtWidgets import (
                QApplication,
                QButtonGroup,
                QComboBox,
                QFrame,
                QGridLayout,
                QHBoxLayout,
                QLabel,
                QMessageBox,
                QPushButton,
                QSizePolicy,
                QScrollBar,
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

        # Qt Multimedia is optional at runtime.  When available it plays the
        # cached source audio, while the monotonic editor clock remains
        # authoritative for visual playback progression. This avoids media-clock
        # stalls truncating playback before Clip Out.
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
                self._camera_drag_from = None
                self._camera_drag_to = None
                self._camera_drag_moved = False
                self._camera_press_x = None
                self.setToolTip(
                    "Seek on the source timeline. Click a Camera Position diamond "
                    "to jump to it; drag the diamond to change its Source Time."
                )

            def _editor_owner(self):
                widget = self.parentWidget()
                while widget is not None:
                    if hasattr(widget, "_pause_playback"):
                        return widget
                    widget = widget.parentWidget()
                return None

            def _time_for_x(self, x):
                owner = self._editor_owner()
                if owner is None or outer.source_duration is None or outer.source_duration <= 0.0:
                    return 0.0
                left = 9.0
                right = max(left + 1.0, float(self.width()) - 9.0)
                fraction = max(0.0, min(1.0, (float(x) - left) / (right - left)))
                return owner.timeline_view.time_for_fraction(fraction)

            def _x_for_time(self, value):
                owner = self._editor_owner()
                left = 9.0
                right = max(left + 1.0, float(self.width()) - 9.0)
                if owner is None or outer.source_duration is None or outer.source_duration <= 0.0:
                    return int(round(left))
                fraction = owner.timeline_view.fraction_for_time(value)
                return int(round(left + fraction * (right - left)))

            def wheelEvent(self, event):
                owner = self._editor_owner()
                if owner is not None:
                    owner._handle_timeline_wheel(event, float(event.position().x()), float(self.width()))
                    event.accept()
                    return
                super().wheelEvent(event)

            def _marker_near_x(self, x, tolerance_px=8.0):
                markers = list(outer.marker_times) + list(outer.dormant_marker_times)
                owner = self._editor_owner()
                if owner is not None and hasattr(owner, "timeline_view"):
                    markers = [
                        value for value in markers
                        if owner.timeline_view.visible_start - 1e-6
                        <= float(value)
                        <= owner.timeline_view.visible_end + 1e-6
                    ]
                if not markers:
                    return None
                nearest = min(markers, key=lambda value: abs(self._x_for_time(value) - float(x)))
                if abs(self._x_for_time(nearest) - float(x)) <= float(tolerance_px):
                    return float(nearest)
                return None

            def mousePressEvent(self, event):
                if event.button() == Qt.MouseButton.LeftButton:
                    owner = self._editor_owner()
                    marker = (
                        self._marker_near_x(event.position().x())
                        if getattr(owner, "editor_mode", "reframe") == "reframe"
                        else None
                    )
                    if marker is not None:
                        if owner is not None:
                            owner._pause_playback()
                            if hasattr(owner, "_flush_reframe_commit"):
                                owner._flush_reframe_commit()
                        self._camera_drag_from = marker
                        self._camera_drag_to = marker
                        self._camera_drag_moved = False
                        self._camera_press_x = float(event.position().x())
                        self.setValue(int(round(marker * 1000.0)))
                        self.update()
                        event.accept()
                        return
                super().mousePressEvent(event)

            def mouseMoveEvent(self, event):
                if self._camera_drag_from is not None:
                    x = float(event.position().x())
                    if (
                        self._camera_press_x is not None
                        and abs(x - self._camera_press_x) >= 3.0
                        and outer.move_position_callback is not None
                    ):
                        self._camera_drag_moved = True
                    if self._camera_drag_moved:
                        target = self._time_for_x(x)
                        self._camera_drag_to = target
                        self.setValue(int(round(target * 1000.0)))
                        self.update()
                    event.accept()
                    return
                super().mouseMoveEvent(event)

            def mouseReleaseEvent(self, event):
                if self._camera_drag_from is not None and event.button() == Qt.MouseButton.LeftButton:
                    original = float(self._camera_drag_from)
                    target = float(
                        self._camera_drag_to
                        if self._camera_drag_to is not None
                        else original
                    )
                    moved = bool(self._camera_drag_moved)
                    self._camera_drag_from = None
                    self._camera_drag_to = None
                    self._camera_drag_moved = False
                    self._camera_press_x = None
                    widget = self._editor_owner()
                    try:
                        if moved and outer.move_position_callback is not None:
                            outer.move_camera_position(original, target)
                            if widget is not None:
                                widget._seek_to(target)
                            else:
                                outer.seek(target)
                        else:
                            # A Camera Position is an addressable edit point.
                            # Clicking its diamond navigates directly to that time.
                            if widget is not None:
                                widget._seek_to(original)
                            else:
                                outer.seek(original)
                    except Exception as exc:
                        outer.last_edit_message = f"Camera Position move failed: {exc}"
                    if widget is not None:
                        widget._refresh()
                    self.update()
                    event.accept()
                    return
                super().mouseReleaseEvent(event)

            def paintEvent(self, event):
                super().paintEvent(event)

                if (
                    outer.source_duration is None
                    or outer.source_duration <= 0.0
                ):
                    return

                owner = self._editor_owner()
                mode = getattr(owner, "editor_mode", "reframe")
                painter = QPainter(self)
                left = 9
                right = max(left + 1, self.width() - 9)
                width = right - left

                def x_for_time(value):
                    if owner is not None and hasattr(owner, "timeline_view"):
                        fraction = owner.timeline_view.fraction_for_time(value)
                    else:
                        fraction = max(
                            0.0,
                            min(1.0, float(value) / outer.source_duration),
                        )
                    return int(round(left + fraction * width))

                band_top = 20
                band_height = max(8, self.height() - 25)

                if mode == "trim":
                    trim_left = x_for_time(outer.trim_start)
                    trim_right = x_for_time(outer.trim_end)
                    inactive = QColor(85, 85, 85, 70)
                    active_band = QColor(70, 145, 230, 90)
                    painter.fillRect(
                        left, band_top, max(0, trim_left - left), band_height, inactive
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

                    boundary = QColor(45, 105, 205)
                    trim_pen = QPen(boundary)
                    trim_pen.setWidth(4)
                    painter.setPen(trim_pen)
                    painter.drawLine(trim_left, 17, trim_left, self.height() - 1)
                    painter.drawLine(trim_right, 17, trim_right, self.height() - 1)

                    flag_width = 34
                    flag_height = 17
                    in_x = max(left, min(right - flag_width, trim_left - flag_width // 2))
                    out_x = max(left, min(right - flag_width, trim_right - flag_width // 2))
                    painter.fillRect(in_x, 0, flag_width, flag_height, boundary)
                    painter.fillRect(out_x, 0, flag_width, flag_height, boundary)
                    painter.setPen(QPen(QColor(255, 255, 255)))
                    painter.drawText(
                        in_x,
                        0,
                        flag_width,
                        flag_height,
                        int(Qt.AlignmentFlag.AlignCenter),
                        "IN",
                    )
                    painter.drawText(
                        out_x,
                        0,
                        flag_width,
                        flag_height,
                        int(Qt.AlignmentFlag.AlignCenter),
                        "OUT",
                    )
                    return

                # Reframe mode: Camera Positions are compact diamond/keyframe
                # markers.  This matches the familiar video-editor convention and
                # keeps the timeline legible without tall marker lines.
                def draw_diamond(marker_time, fill, outline):
                    if owner is not None and hasattr(owner, "timeline_view"):
                        if (
                            float(marker_time) < owner.timeline_view.visible_start - 1e-6
                            or float(marker_time) > owner.timeline_view.visible_end + 1e-6
                        ):
                            return
                    x = x_for_time(marker_time)
                    center_y = 11.0
                    radius = 6.0
                    polygon = QPolygonF([
                        QPointF(float(x), center_y - radius),
                        QPointF(float(x) + radius, center_y),
                        QPointF(float(x), center_y + radius),
                        QPointF(float(x) - radius, center_y),
                    ])
                    painter.setPen(QPen(outline, 1.5))
                    painter.setBrush(fill)
                    painter.drawPolygon(polygon)

                active_marker = outer.camera_position_anchor_time()

                for marker in outer.dormant_marker_times:
                    is_active = (
                        active_marker is not None
                        and abs(float(marker) - active_marker) <= 1e-6
                    )
                    draw_diamond(
                        marker,
                        QColor(63, 124, 255) if is_active else QColor(92, 98, 108),
                        QColor(226, 237, 255) if is_active else QColor(180, 184, 190),
                    )

                for marker in outer.marker_times:
                    is_active = (
                        active_marker is not None
                        and abs(float(marker) - active_marker) <= 1e-6
                    )
                    draw_diamond(
                        marker,
                        QColor(63, 124, 255) if is_active else QColor(225, 78, 78),
                        QColor(226, 237, 255) if is_active else QColor(255, 225, 225),
                    )

                if self._camera_drag_to is not None and self._camera_drag_moved:
                    draw_diamond(
                        self._camera_drag_to,
                        QColor(245, 165, 45),
                        QColor(255, 236, 196),
                    )

        class EditorWidget(QWidget):
            def __init__(self):
                super().__init__()
                self.setWindowTitle(WINDOW_TITLE)
                set_application_icon(QApplication.instance())
                self.setWindowIcon(QIcon(str(application_icon_path())))
                self.setObjectName("panopilotEditor")
                self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                self.setStyleSheet(WORKSPACE_STYLESHEET)
                self.editor_mode = outer.initial_mode
                self._source_pixmap = None
                self.timeline_view = TimelineViewport(
                    outer.source_duration or max(outer.source_time, 0.001),
                    min_visible_duration=max(0.25, 10.0 / max(outer.playback_fps, 1.0)),
                )
                self._timeline_thumbnail_pixmaps = []
                self._timeline_thumbnail_labels = []
                self._timeline_thumbnail_geometry = None
                self._timeline_thumbnail_key = None
                self._timeline_thumbnail_cache = {}
                self._dragging = False
                self._drag_changed = False
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
                self.image_label.setMinimumSize(160, 90)
                # Ignore the pixmap's size hint in both dimensions. The preview
                # must follow the available canvas geometry from the first show,
                # not the initial pre-layout pixmap size.
                self.image_label.setSizePolicy(
                    QSizePolicy.Policy.Ignored,
                    QSizePolicy.Policy.Ignored,
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
                # The preview surface owns the complete media container.
                # The pixmap itself preserves the output aspect ratio, so any
                # letterboxing happens inside this full-size dark surface.
                canvas_layout.addWidget(self.image_label, 1)

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
                self.clip_time_label.setObjectName("editorSecondaryText")

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
                self.camera_label.setObjectName("editorSecondaryText")

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
                    105
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
                self.feedback_label.setObjectName("editorSecondaryText")

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
                    " color: #e7e9ed;"
                    " border: 1px solid #56606d;"
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
                # Precise 360 View Direction controls. Mouse dragging remains
                # the fast free-look gesture; arrows provide deterministic
                # angular nudges for fine framing. In Reframe mode, the GUI
                # batches these into the closest Camera Position to the left.
                # ---------------------------------------------------------
                self.view_step_combo = QComboBox()
                self.view_step_combo.setFocusPolicy(
                    Qt.FocusPolicy.NoFocus
                )
                self.view_step_combo.setToolTip(
                    "Angular step used by the View Direction arrows and "
                    "Shift+Arrow keyboard controls."
                )
                for step_label, step_value in (
                    ("Fine  0.25°", 0.25),
                    ("Normal  1°", 1.0),
                    ("Coarse  5°", 5.0),
                ):
                    self.view_step_combo.addItem(
                        step_label,
                        float(step_value),
                    )
                self.view_step_combo.setCurrentIndex(
                    1
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

                def direction_button(
                    standard_pixmap,
                    tooltip,
                ):
                    button = tool_button(
                        style.standardIcon(
                            standard_pixmap
                        ),
                        tooltip,
                    )
                    button.setFixedSize(
                        34,
                        30,
                    )
                    button.setAutoRepeat(
                        True
                    )
                    button.setAutoRepeatDelay(
                        280
                    )
                    button.setAutoRepeatInterval(
                        75
                    )
                    return button

                self.view_left_button = direction_button(
                    QStyle.StandardPixmap.SP_ArrowLeft,
                    "Look left by the selected angular step (Shift+Left). "
                    "Hold for continuous rotation.",
                )
                self.view_right_button = direction_button(
                    QStyle.StandardPixmap.SP_ArrowRight,
                    "Look right by the selected angular step (Shift+Right). "
                    "Hold for continuous rotation.",
                )
                self.view_up_button = direction_button(
                    QStyle.StandardPixmap.SP_ArrowUp,
                    "Look up by the selected angular step (Shift+Up). "
                    "Hold for continuous rotation.",
                )
                self.view_down_button = direction_button(
                    QStyle.StandardPixmap.SP_ArrowDown,
                    "Look down by the selected angular step (Shift+Down). "
                    "Hold for continuous rotation.",
                )

                def rotation_button(
                    symbol,
                    tooltip,
                ):
                    button = tool_button(
                        None,
                        tooltip,
                        text=symbol,
                    )
                    button.setFixedSize(
                        38,
                        30,
                    )
                    button.setAutoRepeat(
                        True
                    )
                    button.setAutoRepeatDelay(
                        280
                    )
                    button.setAutoRepeatInterval(
                        75
                    )
                    button.setStyleSheet(
                        "font-size: 18px; font-weight: 600;"
                    )
                    return button

                self.view_ccw_button = rotation_button(
                    "↺",
                    "Rotate view counter-clockwise by the selected angular "
                    "step ([). Hold for continuous roll.",
                )
                self.view_cw_button = rotation_button(
                    "↻",
                    "Rotate view clockwise by the selected angular step (]). "
                    "Hold for continuous roll.",
                )

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
                    "◆  Add at Playhead"
                )
                self.use_view_button.setObjectName("primaryAction")
                self.use_view_button.setFocusPolicy(
                    Qt.FocusPolicy.NoFocus
                )
                self.use_view_button.setToolTip(
                    "Create a Camera Position at the current playhead time. "
                    "After a position exists, reframing automatically updates the "
                    "closest Camera Position to the left. (Enter)"
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

                self.view_left_button.clicked.connect(
                    lambda: self._nudge_view(
                        yaw_direction=-1.0
                    )
                )
                self.view_right_button.clicked.connect(
                    lambda: self._nudge_view(
                        yaw_direction=1.0
                    )
                )
                self.view_up_button.clicked.connect(
                    lambda: self._nudge_view(
                        pitch_direction=1.0
                    )
                )
                self.view_down_button.clicked.connect(
                    lambda: self._nudge_view(
                        pitch_direction=-1.0
                    )
                )
                self.view_ccw_button.clicked.connect(
                    lambda: self._nudge_view(
                        roll_direction=-1.0
                    )
                )
                self.view_cw_button.clicked.connect(
                    lambda: self._nudge_view(
                        roll_direction=1.0
                    )
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
                # Workflow-focused layout — 0.49
                #
                # DJI Mimo-inspired hierarchy adapted to desktop:
                #   1. compact Back + Reframe/Trim mode switch,
                #   2. media-dominant preview,
                #   3. contextual controls beside the preview in Reframe,
                #   4. Play immediately beside the timeline.
                # ---------------------------------------------------------
                self.back_button = QToolButton()
                self.back_button.setText(
                    "← Project" if embed_host is not None else "← Close"
                )
                self.back_button.setObjectName("backToProjectAction")
                self.back_button.setToolTip(
                    "Close Clip editing and return to the Project workspace (Esc)"
                )
                self.back_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                self.back_button.clicked.connect(self.close)

                self.reframe_mode_button = QPushButton("Reframe")
                self.trim_mode_button = QPushButton("Trim")
                for mode_button in (self.reframe_mode_button, self.trim_mode_button):
                    mode_button.setCheckable(True)
                    mode_button.setObjectName("modeAction")
                    mode_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                    mode_button.setFixedHeight(30)

                self.mode_group = QButtonGroup(self)
                self.mode_group.setExclusive(True)
                self.mode_group.addButton(self.reframe_mode_button)
                self.mode_group.addButton(self.trim_mode_button)
                self.reframe_mode_button.setChecked(self.editor_mode == "reframe")
                self.trim_mode_button.setChecked(self.editor_mode == "trim")

                # Kept for contextual accessibility text/tooltips; no longer
                # consumes a permanent row in the editor.
                self.mode_hint = QLabel()
                self.mode_hint.hide()

                mode_row = QHBoxLayout()
                mode_row.setContentsMargins(0, 0, 0, 0)
                mode_row.setSpacing(6)
                mode_row.addWidget(self.back_button)
                mode_row.addSpacing(10)
                mode_row.addWidget(self.reframe_mode_button)
                mode_row.addWidget(self.trim_mode_button)
                mode_row.addStretch(1)

                # ---- always-visible fine-camera controls beside preview ----
                # 0.50 removes the disclosure toggle: these are the active tools
                # for Reframe mode, so hiding them only adds interaction cost.
                self.advanced_frame = QFrame()
                self.advanced_frame.setObjectName("advancedCameraPanel")
                advanced_layout = QVBoxLayout(self.advanced_frame)
                advanced_layout.setContentsMargins(0, 2, 0, 0)
                advanced_layout.setSpacing(6)

                camera_state_title = QLabel("Camera")
                camera_state_title.setStyleSheet("font-weight: 600;")
                advanced_layout.addWidget(camera_state_title)
                self.camera_label.setWordWrap(True)
                self.camera_label.setAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                advanced_layout.addWidget(self.camera_label)

                direction_title = QLabel("Direction")
                direction_title.setStyleSheet("font-weight: 600;")
                advanced_layout.addWidget(direction_title)

                direction_pad = QGridLayout()
                direction_pad.setHorizontalSpacing(4)
                direction_pad.setVerticalSpacing(4)
                direction_pad.setContentsMargins(0, 0, 0, 0)
                direction_pad.addWidget(self.view_up_button, 0, 1)
                direction_pad.addWidget(self.view_left_button, 1, 0)
                direction_pad.addWidget(self.view_right_button, 1, 2)
                direction_pad.addWidget(self.view_down_button, 2, 1)
                direction_shell = QHBoxLayout()
                direction_shell.setContentsMargins(0, 0, 0, 0)
                direction_shell.addStretch(1)
                direction_shell.addLayout(direction_pad)
                direction_shell.addStretch(1)
                advanced_layout.addLayout(direction_shell)

                roll_row = QHBoxLayout()
                roll_row.setContentsMargins(0, 0, 0, 0)
                roll_row.setSpacing(5)
                roll_row.addWidget(QLabel("Roll"))
                roll_row.addStretch(1)
                roll_row.addWidget(self.view_ccw_button)
                roll_row.addWidget(self.view_cw_button)
                advanced_layout.addLayout(roll_row)

                step_row = QHBoxLayout()
                step_row.setContentsMargins(0, 0, 0, 0)
                step_row.setSpacing(5)
                step_row.addWidget(QLabel("Step"))
                step_row.addWidget(self.view_step_combo, 1)
                advanced_layout.addLayout(step_row)

                motion_title = QLabel("Motion")
                motion_title.setStyleSheet("font-weight: 600;")
                advanced_layout.addWidget(motion_title)
                advanced_layout.addWidget(self.motion_combo)
                motion_amount_row = QHBoxLayout()
                motion_amount_row.setContentsMargins(0, 0, 0, 0)
                motion_amount_row.setSpacing(5)
                motion_amount_row.addWidget(self.motion_strength_slider, 1)
                motion_amount_row.addWidget(self.motion_strength_label)
                advanced_layout.addLayout(motion_amount_row)
                advanced_layout.addStretch(1)

                self.reframe_frame = QFrame()
                self.reframe_frame.setObjectName("reframeTools")
                self.reframe_frame.setMinimumWidth(180)
                self.reframe_frame.setMaximumWidth(230)
                self.reframe_frame.setSizePolicy(
                    QSizePolicy.Policy.Preferred,
                    QSizePolicy.Policy.Expanding,
                )
                reframe_layout = QVBoxLayout(self.reframe_frame)
                reframe_layout.setContentsMargins(9, 8, 9, 8)
                reframe_layout.setSpacing(7)
                position_header = QHBoxLayout()
                position_header.setContentsMargins(0, 0, 0, 0)
                position_header.setSpacing(5)
                position_title = QLabel("Camera Positions")
                position_title.setStyleSheet("font-weight: 600;")
                position_header.addWidget(position_title)
                position_header.addStretch(1)
                position_header.addWidget(self.camera_position_label)
                position_header.addWidget(self.delete_button)
                reframe_layout.addLayout(position_header)
                reframe_layout.addWidget(self.use_view_button)
                reframe_layout.addWidget(self.advanced_frame, 1)

                preview_row = QHBoxLayout()
                preview_row.setContentsMargins(0, 0, 0, 0)
                preview_row.setSpacing(8)
                preview_row.addWidget(self.canvas, 1)
                preview_row.addWidget(self.reframe_frame, 0)

                # ---- trim-only contextual tools / filmstrip ----
                trim_row = QHBoxLayout()
                trim_row.setContentsMargins(0, 0, 0, 0)
                trim_row.setSpacing(6)
                trim_row.addWidget(self.in_button)
                trim_row.addWidget(self.out_button)
                trim_row.addWidget(self.clear_trim_button)
                trim_row.addSpacing(8)
                trim_row.addWidget(self.trim_in_label)
                trim_row.addWidget(self.trim_duration_label)
                trim_row.addWidget(self.trim_out_label)
                trim_row.addStretch(1)
                trim_row.addWidget(self.clip_time_label)

                self.timeline_thumbnail_frame = QFrame()
                self.timeline_thumbnail_frame.setObjectName("timelineThumbnails")
                self.timeline_thumbnail_layout = QHBoxLayout(self.timeline_thumbnail_frame)
                self.timeline_thumbnail_layout.setContentsMargins(0, 0, 0, 0)
                self.timeline_thumbnail_layout.setSpacing(0)
                self.timeline_thumbnail_frame.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Fixed,
                )
                self.timeline_thumbnail_frame.installEventFilter(self)
                self.timeline_thumbnail_frame.hide()

                self.trim_frame = QFrame()
                self.trim_frame.setObjectName("trimTools")
                trim_layout = QVBoxLayout(self.trim_frame)
                trim_layout.setContentsMargins(0, 0, 0, 0)
                trim_layout.setSpacing(4)
                trim_layout.addLayout(trim_row)
                self.trim_frame.hide()

                # ---- Mimo-style transport: Play is part of the timeline ----
                timeline_row = QHBoxLayout()
                timeline_row.setContentsMargins(0, 0, 0, 0)
                timeline_row.setSpacing(7)
                self.play_button.setFixedSize(36, 32)
                timeline_row.addWidget(self.play_button)
                timeline_row.addWidget(self.slider, 1)
                timeline_row.addWidget(self.time_label)

                # Long-form timeline navigation: the visible time window can
                # zoom around the pointer and pan horizontally. The scrollbar
                # appears as the durable desktop affordance when zoomed.
                self.timeline_scroll = QScrollBar(Qt.Orientation.Horizontal)
                self.timeline_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                self.timeline_scroll.setToolTip(
                    "Horizontal timeline position. Mouse wheel over the timeline zooms; "
                    "Shift+wheel pans; Fit shows the full source."
                )
                self.timeline_zoom_out = QPushButton("−")
                self.timeline_fit = QPushButton("Fit")
                self.timeline_zoom_in = QPushButton("+")
                self.timeline_zoom_label = QLabel("1.0×")
                self.timeline_zoom_label.setObjectName("editorSecondaryText")
                for button in (self.timeline_zoom_out, self.timeline_fit, self.timeline_zoom_in):
                    button.setFixedSize(34 if button is not self.timeline_fit else 44, 26)
                    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

                # Wire navigation only after every timeline widget exists.
                # Keeping construction before signal connections avoids runtime
                # initialization-order failures when the Clip Editor opens.
                self.timeline_scroll.valueChanged.connect(self._timeline_scroll_changed)
                self.timeline_zoom_out.clicked.connect(lambda: self._zoom_timeline(-1.0))
                self.timeline_fit.clicked.connect(self._fit_timeline)
                self.timeline_zoom_in.clicked.connect(lambda: self._zoom_timeline(+1.0))

                timeline_nav_row = QHBoxLayout()
                timeline_nav_row.setContentsMargins(43, 0, 0, 0)
                timeline_nav_row.setSpacing(5)
                timeline_nav_row.addWidget(self.timeline_scroll, 1)
                timeline_nav_row.addWidget(self.timeline_zoom_out)
                timeline_nav_row.addWidget(self.timeline_fit)
                timeline_nav_row.addWidget(self.timeline_zoom_in)
                timeline_nav_row.addWidget(self.timeline_zoom_label)

                if embed_host is None:
                    timeline_row.addWidget(self.project_status_label)
                    timeline_row.addWidget(self.undo_button)
                    timeline_row.addWidget(self.redo_button)
                    timeline_row.addWidget(self.save_button)

                controls_frame = QFrame()
                controls_frame.setObjectName("editorControls")
                controls_frame.setFrameShape(QFrame.Shape.NoFrame)
                controls_layout = QVBoxLayout(controls_frame)
                controls_layout.setContentsMargins(0, 0, 0, 0)
                controls_layout.setSpacing(5)
                controls_layout.addWidget(self.trim_frame)
                controls_layout.addWidget(self.feedback_label)
                controls_layout.addWidget(self.timeline_thumbnail_frame)
                controls_layout.addLayout(timeline_row)
                controls_layout.addLayout(timeline_nav_row)

                layout = QVBoxLayout(self)
                layout.setContentsMargins(8, 7, 8, 7)
                layout.setSpacing(7)
                layout.addLayout(mode_row)
                layout.addLayout(preview_row, 1)
                layout.addWidget(controls_frame, 0)

                # The editor is intentionally shrinkable. The display pixmap
                # scales with the canvas instead of imposing the render size on
                # the top-level window.
                self.setMinimumSize(480, 360)
                if embed_host is None:
                    self.resize(960, 680)

                self.reframe_mode_button.clicked.connect(
                    lambda: self._set_editor_mode("reframe")
                )
                self.trim_mode_button.clicked.connect(
                    lambda: self._set_editor_mode("trim")
                )
                self._set_editor_mode(self.editor_mode)

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

                # Wheel/trackpad events arrive as a burst. Commit the resulting
                # reframing once the gesture settles so Undo gets one meaningful
                # transaction instead of one entry per wheel event.
                self.reframe_commit_timer = QTimer(self)
                self.reframe_commit_timer.setSingleShot(True)
                self.reframe_commit_timer.setInterval(260)
                self.reframe_commit_timer.timeout.connect(
                    self._commit_reframe_to_left
                )

                self.timeline_thumbnail_timer = QTimer(self)
                self.timeline_thumbnail_timer.setSingleShot(True)
                self.timeline_thumbnail_timer.setInterval(110)
                self.timeline_thumbnail_timer.timeout.connect(
                    self._load_timeline_thumbnails_for_view
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

            def _set_editor_mode(self, mode):
                mode = "trim" if str(mode).lower() == "trim" else "reframe"
                if (
                    mode == "trim"
                    and getattr(self, "editor_mode", "reframe") == "reframe"
                    and hasattr(self, "reframe_commit_timer")
                ):
                    self._flush_reframe_commit()
                self.editor_mode = mode
                is_reframe = mode == "reframe"
                self.reframe_mode_button.setChecked(is_reframe)
                self.trim_mode_button.setChecked(not is_reframe)
                self.reframe_frame.setVisible(is_reframe)
                self.trim_frame.setVisible(not is_reframe)
                self.advanced_frame.setVisible(is_reframe)
                # In Trim, the right-side camera rail disappears so the preview
                # immediately expands to the full available width.

                if is_reframe:
                    self.mode_hint.setText(
                        "Reframe: drag or use the fine controls; edits update the closest diamond to the left."
                    )
                    self.slider.setToolTip(
                        "Reframe timeline. Click a Camera Position diamond to jump to it; "
                        "reframing updates the closest diamond to the left. Drag a diamond "
                        "to change when that saved view occurs."
                    )
                else:
                    self.mode_hint.setText(
                        "Trim: choose the source range with Trim In and Trim Out."
                    )
                    self.slider.setToolTip(
                        "Trim timeline. Seek to the desired boundaries, then use Trim In / Trim Out."
                    )

                # A thin media filmstrip is useful navigation context in both
                # workflows, following the media-first pattern used by DJI Mimo.
                self._sync_timeline_view_controls()
                self.slider.update()

            def _sync_timeline_view_controls(self, *, schedule_thumbnails=True):
                start_ms = int(round(self.timeline_view.visible_start * 1000.0))
                end_ms = int(round(self.timeline_view.visible_end * 1000.0))
                if end_ms <= start_ms:
                    end_ms = start_ms + 1
                self.slider.blockSignals(True)
                try:
                    self.slider.setRange(start_ms, end_ms)
                    self.slider.setValue(
                        max(start_ms, min(end_ms, int(round(outer.source_time * 1000.0))))
                    )
                finally:
                    self.slider.blockSignals(False)

                scroll = self.timeline_view.scrollbar_state_ms()
                self.timeline_scroll.blockSignals(True)
                try:
                    self.timeline_scroll.setRange(scroll["minimum"], scroll["maximum"])
                    self.timeline_scroll.setPageStep(scroll["page_step"])
                    self.timeline_scroll.setValue(scroll["value"])
                    self.timeline_scroll.setVisible(not self.timeline_view.is_fitted)
                finally:
                    self.timeline_scroll.blockSignals(False)
                self.timeline_zoom_label.setText(f"{self.timeline_view.zoom_ratio:.1f}×")
                self.timeline_fit.setEnabled(not self.timeline_view.is_fitted)
                self.slider.update()
                if schedule_thumbnails:
                    self._schedule_timeline_thumbnails()

            def _timeline_scroll_changed(self, value):
                if self.timeline_view.is_fitted:
                    return
                self.timeline_view.visible_start = self.timeline_view._clamp_start(float(value) / 1000.0)
                self._sync_timeline_view_controls()

            def _zoom_timeline(self, steps, *, anchor_time=None):
                if anchor_time is None:
                    if self.timeline_view.visible_start <= outer.source_time <= self.timeline_view.visible_end:
                        anchor_time = outer.source_time
                    else:
                        anchor_time = self.timeline_view.visible_start + self.timeline_view.visible_duration / 2.0
                self.timeline_view.zoom_steps(float(steps), anchor_time=anchor_time)
                self._sync_timeline_view_controls()

            def _fit_timeline(self):
                self.timeline_view.fit()
                self._sync_timeline_view_controls()

            def _handle_timeline_wheel(self, event, x, width):
                shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                angle = event.angleDelta()
                pixel = event.pixelDelta()
                horizontal_pixel = (not pixel.isNull()) and abs(pixel.x()) > abs(pixel.y())
                if shift or horizontal_pixel:
                    if horizontal_pixel:
                        fraction = -float(pixel.x()) / max(1.0, float(width))
                    else:
                        fraction = -float(angle.y()) / 120.0 * 0.16
                    self.timeline_view.pan_fraction(fraction)
                    self._sync_timeline_view_controls()
                    return
                steps = float(angle.y()) / 120.0 if angle.y() else (
                    float(pixel.y()) / 30.0 if not pixel.isNull() else 0.0
                )
                if abs(steps) <= 1e-12:
                    return
                left = 9.0
                right = max(left + 1.0, float(width) - 9.0)
                fraction = max(0.0, min(1.0, (float(x) - left) / (right - left)))
                anchor_time = self.timeline_view.time_for_fraction(fraction)
                self._zoom_timeline(steps, anchor_time=anchor_time)

            def _ensure_timeline_playhead_visible(self, source_time):
                if self.timeline_view.ensure_visible(source_time, margin_ratio=0.12):
                    self._sync_timeline_view_controls()

            def _clear_timeline_thumbnail_labels(self):
                while self.timeline_thumbnail_layout.count():
                    item = self.timeline_thumbnail_layout.takeAt(0)
                    widget = item.widget()
                    if widget is not None:
                        widget.deleteLater()
                self._timeline_thumbnail_labels = []

            def _filmstrip_pixmap_for_tile(self, pixmap, width, height):
                scaled = pixmap.scaled(
                    int(width),
                    int(height),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x0 = max(0, (scaled.width() - int(width)) // 2)
                y0 = max(0, (scaled.height() - int(height)) // 2)
                return scaled.copy(x0, y0, int(width), int(height))

            def _timeline_thumbnail_count(self):
                available = max(1, self.timeline_thumbnail_frame.contentsRect().width())
                geometry = filmstrip_tile_geometry(
                    available,
                    height=46,
                    aspect=16 / 9,
                    max_tiles=24,
                )
                return max(1, int(geometry["count"]))

            def _timeline_thumbnail_view_key(self):
                return (
                    round(self.timeline_view.visible_start, 3),
                    round(self.timeline_view.visible_end, 3),
                    self._timeline_thumbnail_count(),
                )

            def _schedule_timeline_thumbnails(self):
                if not outer.cache_media_path:
                    self.timeline_thumbnail_frame.hide()
                    return
                if hasattr(self, "timeline_thumbnail_timer"):
                    self.timeline_thumbnail_timer.start()

            def _load_timeline_thumbnails_for_view(self):
                if not outer.cache_media_path:
                    self.timeline_thumbnail_frame.hide()
                    return
                key = self._timeline_thumbnail_view_key()
                cached = self._timeline_thumbnail_cache.get(key)
                if cached is None:
                    try:
                        samples = sample_video_thumbnails_range(
                            outer.cache_media_path,
                            start_time=self.timeline_view.visible_start,
                            end_time=self.timeline_view.visible_end,
                            count=key[2],
                            width=160,
                            height=90,
                        )
                    except Exception:
                        samples = []
                    pixmaps = []
                    for sample in samples:
                        frame = sample["frame"]
                        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        height, width = rgb.shape[:2]
                        image = QImage(
                            rgb.data,
                            width,
                            height,
                            int(rgb.strides[0]),
                            QImage.Format.Format_RGB888,
                        ).copy()
                        pixmaps.append(QPixmap.fromImage(image))
                    cached = pixmaps
                    self._timeline_thumbnail_cache[key] = cached
                    # Bound presentation cache growth while the User explores a
                    # long source with many zoom/pan windows.
                    while len(self._timeline_thumbnail_cache) > 12:
                        oldest = next(iter(self._timeline_thumbnail_cache))
                        if oldest == key and len(self._timeline_thumbnail_cache) == 1:
                            break
                        self._timeline_thumbnail_cache.pop(oldest, None)
                self._timeline_thumbnail_pixmaps = list(cached)
                self._timeline_thumbnail_key = key
                self._timeline_thumbnail_geometry = None
                self._layout_timeline_thumbnails()

            def _layout_timeline_thumbnails(self):
                if not self._timeline_thumbnail_pixmaps:
                    self.timeline_thumbnail_frame.hide()
                    return

                available = max(1, self.timeline_thumbnail_frame.contentsRect().width())
                geometry = filmstrip_tile_geometry(
                    available,
                    height=46,
                    aspect=16 / 9,
                    max_tiles=len(self._timeline_thumbnail_pixmaps),
                )
                geometry_key = (
                    geometry["count"],
                    geometry["width"],
                    geometry["height"],
                    self._timeline_thumbnail_key,
                )
                if geometry_key == self._timeline_thumbnail_geometry:
                    self.timeline_thumbnail_frame.show()
                    return

                self._timeline_thumbnail_geometry = geometry_key
                self._clear_timeline_thumbnail_labels()
                count = int(geometry["count"])
                tile_w = int(geometry["width"])
                tile_h = int(geometry["height"])
                frame_count = len(self._timeline_thumbnail_pixmaps)
                if count <= 1:
                    indices = [frame_count // 2]
                else:
                    indices = [
                        int(round(i * (frame_count - 1) / float(count - 1)))
                        for i in range(count)
                    ]

                for index in indices:
                    label = QLabel()
                    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    label.setFixedSize(tile_w, tile_h)
                    label.setSizePolicy(
                        QSizePolicy.Policy.Fixed,
                        QSizePolicy.Policy.Fixed,
                    )
                    label.setScaledContents(False)
                    label.setPixmap(
                        self._filmstrip_pixmap_for_tile(
                            self._timeline_thumbnail_pixmaps[index],
                            tile_w,
                            tile_h,
                        )
                    )
                    label.setStyleSheet(
                        "background: #111318; border: 1px solid #303640;"
                    )
                    self.timeline_thumbnail_layout.addWidget(label, 0)
                    self._timeline_thumbnail_labels.append(label)

                self.timeline_thumbnail_frame.setFixedHeight(tile_h)
                self.timeline_thumbnail_frame.show()

            def _update_image_pixmap(self):
                if self._source_pixmap is None:
                    return
                # The canvas is the authoritative available media rectangle. On
                # initial show the QLabel can still report its pre-layout size;
                # using the canvas avoids the first-click resize glitch.
                target = self.canvas.contentsRect().size()
                if target.width() <= 1 or target.height() <= 1:
                    target = self.image_label.size()
                if target.width() <= 1 or target.height() <= 1:
                    return
                self.image_label.setPixmap(
                    self._source_pixmap.scaled(
                        target,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

            def _sync_visible_geometry(self):
                if self.layout() is not None:
                    self.layout().activate()
                if self.canvas.layout() is not None:
                    self.canvas.layout().activate()
                self._update_image_pixmap()
                self._timeline_thumbnail_geometry = None
                self._schedule_timeline_thumbnails()

            def showEvent(self, event):
                super().showEvent(event)
                # Qt may show an embedded editor before its maximized parent has
                # finished assigning final child geometry. Re-fit on the next
                # event-loop turns so the preview spans the canvas immediately.
                QTimer.singleShot(0, self._sync_visible_geometry)
                QTimer.singleShot(40, self._sync_visible_geometry)

            def eventFilter(self, watched, event):
                if (
                    watched is getattr(self, "timeline_thumbnail_frame", None)
                    and event.type() == QEvent.Type.Wheel
                ):
                    self._handle_timeline_wheel(
                        event,
                        float(event.position().x()),
                        float(max(1, self.timeline_thumbnail_frame.width())),
                    )
                    event.accept()
                    return True
                return super().eventFilter(watched, event)

            def resizeEvent(self, event):
                super().resizeEvent(event)
                self._update_image_pixmap()
                self._timeline_thumbnail_geometry = None
                self._schedule_timeline_thumbnails()

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
                        "Preview-only camera — add a Camera Position to keep this view"
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
                    f"{outer.camera_position_count} saved"
                )

                self.camera_label.setText(
                    compact_camera_text(
                        outer.state.yaw_deg,
                        outer.state.pitch_deg,
                        outer.state.fov_deg,
                        outer.state.aspect,
                        roll_deg=outer.state.roll_deg,
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
                self._source_pixmap = QPixmap.fromImage(image)
                self._update_image_pixmap()
                self._sync_timeline_view_controls(schedule_thumbnails=False)
                self._update_time_label()
                self._update_trim_status()
                self._refresh_edit_controls()
                self.slider.update()
                self.update()

            def _seek_to(self, seconds):
                if hasattr(self, "reframe_commit_timer"):
                    self._flush_reframe_commit()
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                try:
                    outer.seek(seconds)
                    self._ensure_timeline_playhead_visible(outer.source_time)
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

            def _commit_reframe_to_left(self):
                if self.editor_mode != "reframe":
                    return False
                try:
                    result = outer.update_left_camera_position()
                except Exception as exc:
                    QMessageBox.critical(
                        self,
                        "PanoPilot — Camera Position failed",
                        str(exc),
                    )
                    return False

                # View pixels are already current; update edit/status surfaces
                # without forcing another panoramic render.
                self._update_trim_status()
                self._refresh_edit_controls()
                self.slider.update()
                return bool(result.get("changed"))

            def _schedule_reframe_commit(self):
                if self.editor_mode == "reframe":
                    self.reframe_commit_timer.start()

            def _flush_reframe_commit(self):
                if self.reframe_commit_timer.isActive():
                    self.reframe_commit_timer.stop()
                    return self._commit_reframe_to_left()
                return False

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
                target = outer.monotonic_playback_target(
                    self._play_anchor_source,
                    self._play_anchor_wall,
                )
                # Audio follows the authoritative editor clock. Correct only
                # meaningful drift; normal QMediaPlayer jitter is left alone.
                if self.media_player is not None:
                    position = self.media_player.position()
                    if position >= 0:
                        position_s = float(position) / 1000.0
                        if abs(position_s - target) > 0.35:
                            self.media_player.setPosition(int(round(target * 1000.0)))
                return target

            def _start_playback(self):
                if outer.playing:
                    return

                self._flush_reframe_commit()
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
                    self._ensure_timeline_playhead_visible(outer.source_time)
                except Exception:
                    self._pause_playback()
                    raise
                self._refresh()

            def _slider_moved(self, value):
                self._update_time_label(float(value) / 1000.0)

            def _slider_released(self):
                self._seek_to(float(self.slider.value()) / 1000.0)

            def _view_step_degrees(self):
                value = self.view_step_combo.currentData()
                try:
                    return max(
                        0.01,
                        float(
                            value
                        ),
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    return 1.0

            def _nudge_view(
                self,
                *,
                yaw_direction=0.0,
                pitch_direction=0.0,
                roll_direction=0.0,
            ):
                self._pause_playback()
                step = self._view_step_degrees()
                outer.state.nudge_view(
                    yaw_delta_deg=(
                        float(
                            yaw_direction
                        )
                        * step
                    ),
                    pitch_delta_deg=(
                        float(
                            pitch_direction
                        )
                        * step
                    ),
                    roll_delta_deg=(
                        float(
                            roll_direction
                        )
                        * step
                    ),
                )
                self._refresh()
                self._schedule_reframe_commit()

            def _image_mouse_press(self, event: QMouseEvent):
                if event.button() == Qt.MouseButton.LeftButton:
                    self._pause_playback()
                    self._flush_reframe_commit()
                    self._dragging = True
                    self._drag_changed = False
                    self._last_pos = event.position()
                    event.accept()

            def _image_mouse_release(self, event: QMouseEvent):
                if event.button() == Qt.MouseButton.LeftButton:
                    changed = bool(self._drag_changed)
                    self._dragging = False
                    self._drag_changed = False
                    self._last_pos = None
                    if changed:
                        # One drag gesture -> one automatic Camera Position edit.
                        self._commit_reframe_to_left()
                    event.accept()

            def _image_mouse_move(self, event: QMouseEvent):
                if self._dragging and self._last_pos is not None:
                    pos = event.position()
                    dx = pos.x() - self._last_pos.x()
                    dy = pos.y() - self._last_pos.y()
                    if abs(dx) > 0.01 or abs(dy) > 0.01:
                        self._drag_changed = True
                    width, _ = outer.view_size
                    displayed = self.image_label.pixmap()
                    displayed_width = (
                        displayed.width()
                        if displayed is not None and not displayed.isNull()
                        else self.image_label.width()
                    )
                    scale = float(width) / max(1.0, float(displayed_width))
                    outer.state.apply_drag(dx * scale, dy * scale, width)
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
                    self._schedule_reframe_commit()
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

                if key == Qt.Key.Key_BracketLeft:
                    self._nudge_view(
                        roll_direction=-1.0
                    )
                    return

                if key == Qt.Key.Key_BracketRight:
                    self._nudge_view(
                        roll_direction=1.0
                    )
                    return

                if shift and key in (
                    Qt.Key.Key_Left,
                    Qt.Key.Key_Right,
                    Qt.Key.Key_Up,
                    Qt.Key.Key_Down,
                ):
                    if key == Qt.Key.Key_Left:
                        self._nudge_view(
                            yaw_direction=-1.0
                        )
                    elif key == Qt.Key.Key_Right:
                        self._nudge_view(
                            yaw_direction=1.0
                        )
                    elif key == Qt.Key.Key_Up:
                        self._nudge_view(
                            pitch_direction=1.0
                        )
                    else:
                        self._nudge_view(
                            pitch_direction=-1.0
                        )
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
                    self._commit_reframe_to_left()
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
                self._flush_reframe_commit()

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

                if on_closed is not None:
                    final_state = outer.result_state()

                    def finish_embedded_close():
                        if embedded_layout is not None:
                            embedded_layout.removeWidget(self)
                        if (
                            embed_host is not None
                            and getattr(embed_host, "_panopilot_editor_widget", None) is self
                        ):
                            delattr(embed_host, "_panopilot_editor_widget")
                        self.setParent(None)
                        self.deleteLater()
                        on_closed(final_state)

                    QTimer.singleShot(0, finish_embedded_close)
                elif window_loop is not None:
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

        window_loop = None
        if on_closed is None:
            window_loop = QEventLoop()

        widget = EditorWidget()
        embedded_layout = None

        if embed_host is not None:
            widget.setParent(embed_host)
            embedded_layout = embed_host.layout()
            if embedded_layout is None:
                embedded_layout = QVBoxLayout(embed_host)
                embedded_layout.setContentsMargins(0, 0, 0, 0)
            embedded_layout.addWidget(widget)
            # Keep a Python reference while Qt owns the child.
            embed_host._panopilot_editor_widget = widget
            widget.show()
            widget.setFocus()
        else:
            widget.showMaximized()
            widget.raise_()
            widget.activateWindow()
            widget.setFocus()

        # Single-Clip callers retain the established blocking contract.
        # Embedded workspaces use the callback path and return immediately,
        # avoiding a nested GUI event loop inside the main application.
        if on_closed is not None:
            return {"embedded": True}

        window_loop.exec()

        if embedded_layout is not None:
            embedded_layout.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()

        return self.result_state()



def explore_osv(
    source,
    *,
    source_time=None,
    yaw_deg=None,
    pitch_deg=None,
    roll_deg=None,
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
    initial_mode="reframe",
    arrange_callback=None,
    embed_host=None,
    on_closed=None,
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

        assert_project_sources(
            session.project,
            clip_ids=[existing_clip.id],
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
    initial_roll = float(roll_deg) if roll_deg is not None else (
        float(
            getattr(
                path_sample.camera,
                "roll_deg",
                0.0,
            )
        )
        if path_sample is not None
        else 0.0
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
            stabilization_amount=float(session.project.stabilization_amount),
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
    initial_roll = float(roll_deg) if roll_deg is not None else (
        float(
            getattr(
                path_sample.camera,
                "roll_deg",
                0.0,
            )
        )
        if path_sample is not None
        else 0.0
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
        roll_deg=initial_roll,
        fov_deg=initial_fov,
        aspect=initial_aspect,
        initial_yaw_deg=initial_yaw,
        initial_pitch_deg=initial_pitch,
        initial_roll_deg=initial_roll,
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
            "stabilization_amount": float(session.project.stabilization_amount),
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
        roll_deg,
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
                    roll_deg=roll_deg,
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
                roll_deg=roll_deg,
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

    def move_position_callback(*, source_time, new_source_time):
        if active_clip_id is None:
            raise RuntimeError("Camera Position timeline move requires a Clip-id based editor")
        frame_tolerance = max(
            0.001,
            0.51 / float(
                cache_reader.fps if cache_reader is not None else max(preview_fps, 1.0)
            ),
        )
        transaction = session.move_camera_position_from_clip(
            active_clip_id,
            source_time=source_time,
            new_source_time=new_source_time,
            source_duration=source_duration,
            tolerance_s=frame_tolerance,
        )
        return session_payload(
            transaction,
            source_time=new_source_time,
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
        move_position_callback=move_position_callback,
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
        initial_mode=initial_mode,
        arrange_callback=arrange_callback,
    )

    window._apply_project_state(
        session_payload()
    )

    def final_payload(final_state):
        clip = current_clip()
        return {
            "source": str(source),
            "clip_id": (
                active_clip_id
                if active_clip_id is not None
                else (clip.id if clip is not None else None)
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

    if on_closed is not None:
        if embed_host is None:
            raise ValueError("on_closed requires embed_host")

        def embedded_closed(final_state):
            try:
                on_closed(final_payload(final_state))
            finally:
                if cache_reader is not None:
                    cache_reader.close()

        try:
            window.run(
                embed_host=embed_host,
                on_closed=embedded_closed,
            )
        except Exception:
            if cache_reader is not None:
                cache_reader.close()
            raise
        return {
            "source": str(source),
            "clip_id": active_clip_id,
            "project_path": str(project_path),
            "embedded": True,
        }

    try:
        final_state = window.run(embed_host=embed_host)
        return final_payload(final_state)
    finally:
        if cache_reader is not None:
            cache_reader.close()
