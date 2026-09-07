"""
Transactional PanoPilot project editing session.

0.16 separates in-memory edits from persistence:

    edit -> dirty project + undo history
    save -> atomic project write + clean baseline

Navigation/exploration never enters this history.

The history is snapshot-based for Iteration 1.  The project model is currently
small, so whole-project snapshots provide deterministic undo/redo semantics and
make transaction boundaries explicit without prematurely introducing a command
serialization framework.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from .project import (
    Project,
    TIME_MATCH_TOLERANCE_S,
    commit_camera_position,
    commit_camera_position_to_clip,
    save_project,
)


@dataclass(frozen=True)
class HistoryEntry:
    label: str
    before: dict
    after: dict


class ProjectSession:
    def __init__(self, project: Project, *, path=None):
        self.project = project
        self.path = Path(path) if path is not None else None
        self._saved_snapshot = self._snapshot()
        self._undo_stack: list[HistoryEntry] = []
        self._redo_stack: list[HistoryEntry] = []

    def _snapshot(self):
        return deepcopy(self.project.to_dict())

    def _restore(self, snapshot):
        self.project = Project.from_dict(deepcopy(snapshot))

    @property
    def dirty(self):
        return self._snapshot() != self._saved_snapshot

    @property
    def can_undo(self):
        return bool(self._undo_stack)

    @property
    def can_redo(self):
        return bool(self._redo_stack)

    @property
    def undo_label(self):
        return self._undo_stack[-1].label if self._undo_stack else None

    @property
    def redo_label(self):
        return self._redo_stack[-1].label if self._redo_stack else None

    def state(self):
        return {
            "dirty": bool(self.dirty),
            "can_undo": bool(self.can_undo),
            "can_redo": bool(self.can_redo),
            "undo_label": self.undo_label,
            "redo_label": self.redo_label,
        }

    def transact(self, label, mutator):
        before = self._snapshot()
        result = mutator(self.project)
        after = self._snapshot()

        changed = before != after

        if changed:
            self._undo_stack.append(
                HistoryEntry(
                    label=str(label),
                    before=before,
                    after=after,
                )
            )
            # A new edit after undo creates a new branch.
            self._redo_stack.clear()

        return {
            "changed": bool(changed),
            "label": str(label),
            "result": result,
            **self.state(),
        }

    def undo(self):
        if not self._undo_stack:
            return {
                "changed": False,
                "label": None,
                "result": None,
                **self.state(),
            }

        entry = self._undo_stack.pop()
        self._restore(entry.before)
        self._redo_stack.append(entry)

        return {
            "changed": True,
            "label": entry.label,
            "result": None,
            **self.state(),
        }

    def redo(self):
        if not self._redo_stack:
            return {
                "changed": False,
                "label": None,
                "result": None,
                **self.state(),
            }

        entry = self._redo_stack.pop()
        self._restore(entry.after)
        self._undo_stack.append(entry)

        return {
            "changed": True,
            "label": entry.label,
            "result": None,
            **self.state(),
        }

    def save(self, path=None):
        target = Path(path) if path is not None else self.path

        if target is None:
            raise ValueError("A project path is required to save")

        save_project(self.project, target)
        self.path = target
        self._saved_snapshot = self._snapshot()

        return {
            "saved": True,
            "path": str(target),
            **self.state(),
        }

    def discard_to_saved(self):
        changed = self.dirty
        self._restore(self._saved_snapshot)
        self._undo_stack.clear()
        self._redo_stack.clear()

        return {
            "changed": bool(changed),
            "discarded": bool(changed),
            **self.state(),
        }

    def commit_camera_position(
        self,
        source,
        *,
        source_time,
        yaw_deg,
        pitch_deg,
        fov_deg,
        output_aspect=None,
    ):
        return self.transact(
            "Use this view",
            lambda project: commit_camera_position(
                project,
                source,
                source_time=source_time,
                yaw_deg=yaw_deg,
                pitch_deg=pitch_deg,
                fov_deg=fov_deg,
                output_aspect=output_aspect,
            ),
        )

    def commit_camera_position_to_clip(
        self,
        clip_id,
        *,
        source_time,
        yaw_deg,
        pitch_deg,
        fov_deg,
        output_aspect=None,
    ):
        return self.transact(
            "Use this view",
            lambda project: (
                commit_camera_position_to_clip(
                    project,
                    clip_id,
                    source_time=source_time,
                    yaw_deg=yaw_deg,
                    pitch_deg=pitch_deg,
                    fov_deg=fov_deg,
                    output_aspect=output_aspect,
                )
            ),
        )

    def set_output_aspect(self, aspect):
        if aspect not in ("16:9", "9:16"):
            raise ValueError("aspect must be '16:9' or '9:16'")

        def mutate(project):
            previous = project.output_aspect
            project.output_aspect = aspect
            return {
                "previous_aspect": previous,
                "aspect": aspect,
            }

        return self.transact(
            "Output frame",
            mutate,
        )

    def set_output_resolution(self, resolution):
        def mutate(project):
            previous = str(
                project.output_resolution
            )
            current = project.set_output_resolution(
                resolution
            )
            return {
                "previous_resolution": previous,
                "resolution": current[
                    "resolution"
                ],
            }

        return self.transact(
            "Output resolution",
            mutate,
        )

    def set_output_quality(self, quality):
        def mutate(project):
            previous = str(
                project.output_quality
            )
            current = project.set_output_quality(
                quality
            )
            return {
                "previous_quality": previous,
                "quality": current[
                    "quality"
                ],
            }

        return self.transact(
            "Export quality",
            mutate,
        )

    def set_camera_motion(
        self,
        *,
        easing=None,
        strength=None,
    ):
        def mutate(project):
            previous = {
                "easing": project.camera_motion_easing,
                "strength": float(
                    project.camera_motion_strength
                ),
            }

            current = project.set_camera_motion(
                easing=easing,
                strength=strength,
            )

            return {
                "previous": previous,
                "camera_motion_easing": current["easing"],
                "camera_motion_strength": float(
                    current["strength"]
                ),
            }

        return self.transact(
            "Camera motion",
            mutate,
        )

    def set_stabilization_amount(self, amount):
        def mutate(project):
            previous = float(project.stabilization_amount)
            current = project.set_stabilization_amount(amount)
            return {
                "previous_stabilization_amount": previous,
                "stabilization_amount": float(current["amount"]),
            }

        return self.transact("Stabilization", mutate)


    def delete_camera_position_from_clip(
        self,
        clip_id,
        *,
        source_time,
        tolerance_s=TIME_MATCH_TOLERANCE_S,
    ):
        clip_id = str(clip_id)
        target_time = float(source_time)
        tolerance_s = max(
            TIME_MATCH_TOLERANCE_S,
            float(tolerance_s),
        )

        def mutate(project):
            clip = project.clip_for_id(
                clip_id
            )

            if (
                clip is None
                or not clip.camera_positions
            ):
                return {
                    "deleted": False,
                    "reason": "no-camera-positions",
                    "clip_id": clip_id,
                }

            candidates = sorted(
                (
                    (
                        abs(
                            float(
                                position.source_time
                            )
                            - target_time
                        ),
                        index,
                        position,
                    )
                    for index, position
                    in enumerate(
                        clip.camera_positions
                    )
                ),
                key=lambda item: item[0],
            )

            distance, index, position = (
                candidates[0]
            )

            if distance > tolerance_s:
                return {
                    "deleted": False,
                    "reason": "no-position-at-current-time",
                    "nearest_distance_s": (
                        float(distance)
                    ),
                    "clip_id": clip_id,
                }

            deleted = position.to_dict()
            del clip.camera_positions[index]

            return {
                "deleted": True,
                "camera_position": deleted,
                "distance_s": float(distance),
                "clip_id": clip_id,
            }

        return self.transact(
            "Delete Camera Position",
            mutate,
        )

    def delete_camera_position(
        self,
        source,
        *,
        source_time,
        tolerance_s=TIME_MATCH_TOLERANCE_S,
    ):
        source = str(source)
        target_time = float(source_time)
        tolerance_s = max(
            TIME_MATCH_TOLERANCE_S,
            float(tolerance_s),
        )

        def mutate(project):
            clip = project.clip_for_source(
                source,
                create=False,
            )

            if clip is None or not clip.camera_positions:
                return {
                    "deleted": False,
                    "reason": "no-camera-positions",
                }

            candidates = sorted(
                (
                    (
                        abs(float(position.source_time) - target_time),
                        index,
                        position,
                    )
                    for index, position in enumerate(
                        clip.camera_positions
                    )
                ),
                key=lambda item: item[0],
            )

            distance, index, position = candidates[0]

            if distance > tolerance_s:
                return {
                    "deleted": False,
                    "reason": "no-position-at-current-time",
                    "nearest_distance_s": float(distance),
                }

            deleted = position.to_dict()
            del clip.camera_positions[index]

            # A Clip may also exist because it owns trim metadata. Remove an
            # empty Clip only when it has no non-default Clip state.
            if not clip.camera_positions and clip.has_default_trim:
                project.clips.remove(clip)

            return {
                "deleted": True,
                "camera_position": deleted,
                "distance_s": float(distance),
            }

        return self.transact(
            "Delete Camera Position",
            mutate,
        )

    def set_clip_trim_in(
        self,
        source,
        *,
        source_time,
        source_duration,
        min_duration_s=0.001,
    ):
        source = str(source)
        source_time = max(0.0, float(source_time))
        source_duration = float(source_duration)
        min_duration_s = max(1e-6, float(min_duration_s))

        def mutate(project):
            clip = project.clip_for_source(source, create=True)
            out_time = (
                source_duration
                if clip.trim_out_source_time is None
                else float(clip.trim_out_source_time)
            )
            new_in = 0.0 if source_time <= 1e-6 else source_time
            if out_time - new_in < min_duration_s:
                raise ValueError("Clip In must be before Clip Out")
            previous = float(clip.trim_in_source_time)
            clip.trim_in_source_time = new_in
            return {
                "previous_in_source_time": previous,
                "in_source_time": new_in,
                "out_source_time": clip.trim_out_source_time,
            }

        return self.transact("Set Clip In", mutate)

    def set_clip_trim_out(
        self,
        source,
        *,
        source_time,
        source_duration,
        min_duration_s=0.001,
    ):
        source = str(source)
        source_duration = float(source_duration)
        source_time = min(source_duration, max(0.0, float(source_time)))
        min_duration_s = max(1e-6, float(min_duration_s))

        def mutate(project):
            clip = project.clip_for_source(source, create=True)
            if source_time - clip.trim_in_source_time < min_duration_s:
                raise ValueError("Clip Out must be after Clip In")
            previous = clip.trim_out_source_time
            new_out = None if source_duration - source_time <= 1e-6 else source_time
            clip.trim_out_source_time = new_out
            return {
                "previous_out_source_time": previous,
                "in_source_time": float(clip.trim_in_source_time),
                "out_source_time": new_out,
            }

        return self.transact("Set Clip Out", mutate)

    def clear_clip_trim(self, source):
        source = str(source)

        def mutate(project):
            clip = project.clip_for_source(source, create=False)
            if clip is None:
                return {"cleared": False, "reason": "no-clip"}
            previous = {
                "in_source_time": float(clip.trim_in_source_time),
                "out_source_time": clip.trim_out_source_time,
            }
            clip.trim_in_source_time = 0.0
            clip.trim_out_source_time = None
            if not clip.camera_positions and clip.has_default_trim:
                project.clips.remove(clip)
            return {
                "cleared": True,
                "previous": previous,
                "in_source_time": 0.0,
                "out_source_time": None,
            }

        return self.transact("Clear Clip Trim", mutate)

    def add_clip(
        self,
        source,
        *,
        allow_duplicate_source=False,
    ):
        source = str(source)

        def mutate(project):
            clip = project.add_clip(
                source,
                allow_duplicate_source=(
                    allow_duplicate_source
                ),
            )

            return {
                "added": True,
                "clip": clip.to_dict(),
                "clip_id": clip.id,
            }

        return self.transact(
            "Add Clip",
            mutate,
        )

    def remove_clip(self, clip_id):
        clip_id = str(clip_id)

        def mutate(project):
            removed = project.remove_clip(
                clip_id
            )

            if removed is None:
                return {
                    "removed": False,
                    "reason": "unknown-clip",
                    "clip_id": clip_id,
                }

            return {
                "removed": True,
                "clip": removed.to_dict(),
                "clip_id": clip_id,
            }

        return self.transact(
            "Remove Clip",
            mutate,
        )

    def move_clip(self, clip_id, new_index):
        clip_id = str(clip_id)
        new_index = int(new_index)

        def mutate(project):
            old_index = project.clip_index(
                clip_id
            )

            if old_index is None:
                return {
                    "moved": False,
                    "reason": "unknown-clip",
                    "clip_id": clip_id,
                }

            final_index = project.move_clip(
                clip_id,
                new_index,
            )

            return {
                "moved": (
                    final_index
                    != old_index
                ),
                "clip_id": clip_id,
                "old_index": old_index,
                "new_index": final_index,
            }

        return self.transact(
            "Reorder Clip",
            mutate,
        )

    def move_clip_by(self, clip_id, delta):
        index = self.project.clip_index(
            clip_id
        )

        if index is None:
            return {
                "changed": False,
                "label": "Reorder Clip",
                "result": {
                    "moved": False,
                    "reason": "unknown-clip",
                    "clip_id": str(clip_id),
                },
                **self.state(),
            }

        return self.move_clip(
            clip_id,
            index + int(delta),
        )

    def set_clip_trim_in_by_id(
        self,
        clip_id,
        *,
        source_time,
        source_duration,
        min_duration_s=0.001,
    ):
        clip_id = str(clip_id)
        source_time = max(
            0.0,
            float(source_time),
        )
        source_duration = float(
            source_duration
        )
        min_duration_s = max(
            1e-6,
            float(min_duration_s),
        )

        def mutate(project):
            clip = project.clip_for_id(
                clip_id
            )

            if clip is None:
                raise ValueError(
                    f"Unknown Clip id: {clip_id}"
                )

            out_time = (
                source_duration
                if clip.trim_out_source_time
                is None
                else float(
                    clip.trim_out_source_time
                )
            )
            new_in = (
                0.0
                if source_time <= 1e-6
                else source_time
            )

            if (
                out_time - new_in
                < min_duration_s
            ):
                raise ValueError(
                    "Clip In must be before Clip Out"
                )

            previous = float(
                clip.trim_in_source_time
            )
            clip.trim_in_source_time = (
                new_in
            )

            return {
                "clip_id": clip_id,
                "previous_in_source_time": previous,
                "in_source_time": new_in,
                "out_source_time": (
                    clip.trim_out_source_time
                ),
            }

        return self.transact(
            "Set Clip In",
            mutate,
        )

    def set_clip_trim_out_by_id(
        self,
        clip_id,
        *,
        source_time,
        source_duration,
        min_duration_s=0.001,
    ):
        clip_id = str(clip_id)
        source_duration = float(
            source_duration
        )
        source_time = min(
            source_duration,
            max(
                0.0,
                float(source_time),
            ),
        )
        min_duration_s = max(
            1e-6,
            float(min_duration_s),
        )

        def mutate(project):
            clip = project.clip_for_id(
                clip_id
            )

            if clip is None:
                raise ValueError(
                    f"Unknown Clip id: {clip_id}"
                )

            if (
                source_time
                - clip.trim_in_source_time
                < min_duration_s
            ):
                raise ValueError(
                    "Clip Out must be after Clip In"
                )

            previous = (
                clip.trim_out_source_time
            )

            new_out = (
                None
                if (
                    source_duration
                    - source_time
                    <= 1e-6
                )
                else source_time
            )

            clip.trim_out_source_time = (
                new_out
            )

            return {
                "clip_id": clip_id,
                "previous_out_source_time": previous,
                "in_source_time": float(
                    clip.trim_in_source_time
                ),
                "out_source_time": new_out,
            }

        return self.transact(
            "Set Clip Out",
            mutate,
        )

    def clear_clip_trim_by_id(
        self,
        clip_id,
    ):
        clip_id = str(clip_id)

        def mutate(project):
            clip = project.clip_for_id(
                clip_id
            )

            if clip is None:
                return {
                    "cleared": False,
                    "reason": "no-clip",
                    "clip_id": clip_id,
                }

            previous = {
                "in_source_time": float(
                    clip.trim_in_source_time
                ),
                "out_source_time": (
                    clip.trim_out_source_time
                ),
            }

            clip.trim_in_source_time = 0.0
            clip.trim_out_source_time = None

            return {
                "cleared": True,
                "clip_id": clip_id,
                "previous": previous,
                "in_source_time": 0.0,
                "out_source_time": None,
            }

        return self.transact(
            "Clear Clip Trim",
            mutate,
        )
