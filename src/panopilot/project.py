"""
PanoPilot project model.

Project schema v3 adds persisted Camera Motion easing settings while
preserving the schema-v2 continuous trim range per Clip and
preserving the fundamental reframing invariant:

    Camera Position source_time is authoritative.
    Changing Clip trim never retimes Camera Positions.

A Camera Position outside the active trim remains persisted and becomes
dormant. Expanding the trim later can make it active again.

Schema v1/v2 projects are upgraded in memory automatically and are written as v3
on their next explicit Save.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
from pathlib import Path
from typing import Optional


SCHEMA_VERSION = 3
SUPPORTED_SCHEMA_VERSIONS = (1, 2, 3)
TIME_MATCH_TOLERANCE_S = 1e-6

CAMERA_MOTION_EASINGS = (
    "smooth",
    "ease-in-out",
    "ease-in",
    "ease-out",
    "linear",
)
DEFAULT_CAMERA_MOTION_EASING = "smooth"
DEFAULT_CAMERA_MOTION_STRENGTH = 1.0

PROJECT_BACKUP_SCHEMA_VERSION = 1
PROJECT_BACKUP_KEEP = 25


@dataclass
class CameraPosition:
    source_time: float
    yaw_deg: float
    pitch_deg: float
    fov_deg: float

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(
            source_time=float(data["source_time"]),
            yaw_deg=float(data["yaw_deg"]),
            pitch_deg=float(data["pitch_deg"]),
            fov_deg=float(data["fov_deg"]),
        )


@dataclass
class Clip:
    id: str
    source: str
    camera_positions: list[CameraPosition] = field(default_factory=list)
    trim_in_source_time: float = 0.0
    trim_out_source_time: Optional[float] = None

    def __post_init__(self):
        self.trim_in_source_time = float(self.trim_in_source_time)
        if self.trim_in_source_time < 0.0:
            raise ValueError("Clip trim In must be >= 0")

        if self.trim_out_source_time is not None:
            self.trim_out_source_time = float(self.trim_out_source_time)
            if self.trim_out_source_time <= self.trim_in_source_time:
                raise ValueError("Clip trim Out must be greater than trim In")

        self.sort_positions()

    @property
    def has_default_trim(self):
        return (
            abs(self.trim_in_source_time) <= TIME_MATCH_TOLERANCE_S
            and self.trim_out_source_time is None
        )

    def sort_positions(self):
        self.camera_positions.sort(key=lambda p: p.source_time)

    def position_at(self, source_time: float) -> Optional[CameraPosition]:
        target = float(source_time)
        for position in self.camera_positions:
            if abs(position.source_time - target) <= TIME_MATCH_TOLERANCE_S:
                return position
        return None

    def resolved_trim_out(self, source_duration):
        source_duration = float(source_duration)
        if source_duration <= 0.0:
            raise ValueError("source_duration must be greater than zero")

        out_time = (
            source_duration
            if self.trim_out_source_time is None
            else float(self.trim_out_source_time)
        )

        if out_time > source_duration + TIME_MATCH_TOLERANCE_S:
            raise ValueError("Clip trim Out exceeds current source duration")
        if out_time - self.trim_in_source_time <= TIME_MATCH_TOLERANCE_S:
            raise ValueError("Clip active trim must have positive duration")

        return min(out_time, source_duration)

    def resolved_trim_bounds(self, source_duration):
        return float(self.trim_in_source_time), self.resolved_trim_out(source_duration)

    def clip_duration(self, source_duration):
        start, end = self.resolved_trim_bounds(source_duration)
        return end - start

    def source_to_clip_time(self, source_time):
        return float(source_time) - float(self.trim_in_source_time)

    def clip_to_source_time(self, clip_time):
        return float(self.trim_in_source_time) + float(clip_time)

    def is_source_time_active(self, source_time, *, source_duration=None):
        value = float(source_time)
        if value < self.trim_in_source_time - TIME_MATCH_TOLERANCE_S:
            return False
        if self.trim_out_source_time is not None:
            return value <= self.trim_out_source_time + TIME_MATCH_TOLERANCE_S
        if source_duration is not None:
            return value <= float(source_duration) + TIME_MATCH_TOLERANCE_S
        return True

    def active_camera_positions(self):
        return [
            p for p in self.camera_positions
            if self.is_source_time_active(p.source_time)
        ]

    def dormant_camera_positions(self):
        return [
            p for p in self.camera_positions
            if not self.is_source_time_active(p.source_time)
        ]

    def upsert_camera_position(self, source_time, yaw_deg, pitch_deg, fov_deg):
        existing = self.position_at(source_time)
        if existing is None:
            position = CameraPosition(
                source_time=float(source_time),
                yaw_deg=float(yaw_deg),
                pitch_deg=float(pitch_deg),
                fov_deg=float(fov_deg),
            )
            self.camera_positions.append(position)
            self.sort_positions()
            created = True
        else:
            existing.yaw_deg = float(yaw_deg)
            existing.pitch_deg = float(pitch_deg)
            existing.fov_deg = float(fov_deg)
            position = existing
            created = False
        return position, created

    def to_dict(self):
        self.sort_positions()
        return {
            "id": self.id,
            "source": self.source,
            "trim": {
                "in_source_time": float(self.trim_in_source_time),
                "out_source_time": (
                    float(self.trim_out_source_time)
                    if self.trim_out_source_time is not None
                    else None
                ),
            },
            "camera_positions": [p.to_dict() for p in self.camera_positions],
        }

    @classmethod
    def from_dict(cls, data):
        trim = data.get("trim") or {}
        return cls(
            id=str(data["id"]),
            source=str(data["source"]),
            trim_in_source_time=float(trim.get("in_source_time", 0.0)),
            trim_out_source_time=(
                float(trim["out_source_time"])
                if trim.get("out_source_time") is not None
                else None
            ),
            camera_positions=[
                CameraPosition.from_dict(p)
                for p in data.get("camera_positions", [])
            ],
        )


@dataclass
class Project:
    output_aspect: str = "16:9"
    clips: list[Clip] = field(default_factory=list)
    camera_motion_easing: str = DEFAULT_CAMERA_MOTION_EASING
    camera_motion_strength: float = DEFAULT_CAMERA_MOTION_STRENGTH
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        if self.output_aspect not in ("16:9", "9:16"):
            raise ValueError("output_aspect must be '16:9' or '9:16'")

        self.set_camera_motion(
            easing=self.camera_motion_easing,
            strength=self.camera_motion_strength,
        )
        self.schema_version = SCHEMA_VERSION

    def set_camera_motion(self, *, easing=None, strength=None):
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

        if easing not in CAMERA_MOTION_EASINGS:
            raise ValueError(
                "camera motion easing must be one of: "
                + ", ".join(CAMERA_MOTION_EASINGS)
            )

        if not 0.0 <= strength <= 1.0:
            raise ValueError(
                "camera motion strength must be between 0 and 1"
            )

        self.camera_motion_easing = easing
        self.camera_motion_strength = strength

        return {
            "easing": easing,
            "strength": strength,
        }

    def clip_for_id(self, clip_id):
        clip_id = str(clip_id)

        for clip in self.clips:
            if clip.id == clip_id:
                return clip

        return None

    def clip_index(self, clip_id):
        clip_id = str(clip_id)

        for index, clip in enumerate(self.clips):
            if clip.id == clip_id:
                return index

        return None

    def clips_for_source(self, source):
        source = str(source)

        return [
            clip
            for clip in self.clips
            if clip.source == source
        ]

    def clip_for_source(self, source, *, create=False):
        """
        Compatibility helper returning the first Clip for a source.

        0.18 deliberately keeps repeated instances of the same source out of
        scope, so ordinary project creation still has at most one Clip per
        source. The persistent domain model is nevertheless Clip-id based.
        """
        source = str(source)

        for clip in self.clips:
            if clip.source == source:
                return clip

        if not create:
            return None

        return self.add_clip(source)

    def next_clip_id(self):
        used = {
            clip.id
            for clip in self.clips
        }

        numeric = []

        for clip_id in used:
            match = re.fullmatch(
                r"clip-(\d+)",
                clip_id,
            )

            if match:
                numeric.append(
                    int(match.group(1))
                )

        candidate = (
            max(numeric, default=0) + 1
        )

        while (
            f"clip-{candidate}" in used
        ):
            candidate += 1

        return f"clip-{candidate}"

    def add_clip(
        self,
        source,
        *,
        allow_duplicate_source=False,
    ):
        source = str(source)

        if (
            not allow_duplicate_source
            and self.clips_for_source(source)
        ):
            raise ValueError(
                "This source is already present in the project. "
                "Repeated source instances are not part of Iteration 1."
            )

        clip = Clip(
            id=self.next_clip_id(),
            source=source,
        )
        self.clips.append(clip)
        return clip

    def remove_clip(self, clip_id):
        index = self.clip_index(clip_id)

        if index is None:
            return None

        return self.clips.pop(index)

    def move_clip(self, clip_id, new_index):
        index = self.clip_index(clip_id)

        if index is None:
            raise ValueError(
                f"Unknown Clip id: {clip_id}"
            )

        if not self.clips:
            return 0

        target = max(
            0,
            min(
                int(new_index),
                len(self.clips) - 1,
            ),
        )

        if target == index:
            return index

        clip = self.clips.pop(index)
        self.clips.insert(target, clip)
        return target

    def to_dict(self):
        return {
            "schema_version": SCHEMA_VERSION,
            "output_frame": {"aspect": self.output_aspect},
            "camera_motion": {
                "easing": self.camera_motion_easing,
                "strength": float(
                    self.camera_motion_strength
                ),
            },
            "clips": [clip.to_dict() for clip in self.clips],
        }

    @classmethod
    def from_dict(cls, data):
        version = int(data.get("schema_version", 1))
        if version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"Unsupported project schema_version {version}; "
                f"supported: {SUPPORTED_SCHEMA_VERSIONS}"
            )
        output_frame = data.get("output_frame", {})
        camera_motion = data.get("camera_motion") or {}

        return cls(
            output_aspect=str(output_frame.get("aspect", "16:9")),
            clips=[Clip.from_dict(clip) for clip in data.get("clips", [])],
            camera_motion_easing=str(
                camera_motion.get(
                    "easing",
                    DEFAULT_CAMERA_MOTION_EASING,
                )
            ),
            camera_motion_strength=float(
                camera_motion.get(
                    "strength",
                    DEFAULT_CAMERA_MOTION_STRENGTH,
                )
            ),
            schema_version=SCHEMA_VERSION,
        )



def _normalized_source_path(value):
    """Best-effort filesystem identity used only for command resolution."""
    try:
        return Path(value).expanduser().resolve(strict=False)
    except Exception:
        return None


def resolve_project_clip(project: Project, selector):
    """
    Resolve one Clip by stable Clip id first, then source identity.

    Source-path matching accepts unambiguous absolute/relative aliases.
    """
    selector = str(selector)

    clip = project.clip_for_id(selector)
    if clip is not None:
        return clip

    exact = [
        item
        for item in project.clips
        if item.source == selector
    ]

    if len(exact) == 1:
        return exact[0]

    if len(exact) > 1:
        raise ValueError(
            f"Selector {selector!r} matches multiple Clips; use a Clip id"
        )

    target = _normalized_source_path(selector)

    if target is not None:
        matches = []

        for item in project.clips:
            candidate = _normalized_source_path(
                item.source
            )

            if candidate == target:
                matches.append(item)

        if len(matches) == 1:
            return matches[0]

        if len(matches) > 1:
            raise ValueError(
                f"Source path {selector!r} matches multiple Clips; use a Clip id"
            )

    available = ", ".join(
        f"{item.id}={item.source}"
        for item in project.clips
    ) or "(project has no Clips)"

    raise ValueError(
        f"Project has no Clip matching {selector!r}. "
        f"Available Clips: {available}"
    )


def commit_camera_position_to_clip(
    project: Project,
    clip_id,
    *,
    source_time,
    yaw_deg,
    pitch_deg,
    fov_deg,
    output_aspect=None,
):
    """Commit a Camera Position to one exact Clip instance."""
    clip = project.clip_for_id(
        str(clip_id)
    )

    if clip is None:
        raise ValueError(
            f"Unknown Clip id: {clip_id}"
        )

    position, created = (
        clip.upsert_camera_position(
            source_time=source_time,
            yaw_deg=yaw_deg,
            pitch_deg=pitch_deg,
            fov_deg=fov_deg,
        )
    )

    if output_aspect is not None:
        if output_aspect not in (
            "16:9",
            "9:16",
        ):
            raise ValueError(
                "output_aspect must be '16:9' or '9:16'"
            )
        project.output_aspect = (
            output_aspect
        )

    index = clip.camera_positions.index(
        position
    )

    return {
        "created": bool(created),
        "clip_id": clip.id,
        "position_index": index,
        "position_number": index + 1,
        "camera_position": (
            position.to_dict()
        ),
        "active_in_trim": (
            clip.is_source_time_active(
                position.source_time
            )
        ),
    }



def _project_json_text(project: Project):
    return (
        json.dumps(
            project.to_dict(),
            indent=2,
        )
        + "\n"
    )


def default_project_backup_root():
    """
    Durable backup root outside the source checkout.

    XDG_DATA_HOME is used when configured; otherwise Linux defaults to:
      ~/.local/share/panopilot/project-backups
    """
    xdg = os.environ.get(
        "XDG_DATA_HOME"
    )
    base = (
        Path(xdg)
        if xdg
        else Path.home()
        / ".local"
        / "share"
    )

    return (
        base
        / "panopilot"
        / "project-backups"
    )


def project_backup_directory(
    project_path,
    *,
    backup_root=None,
):
    project_path = Path(
        project_path
    ).expanduser()

    absolute = str(
        project_path.resolve(
            strict=False
        )
    )
    key = sha256(
        absolute.encode(
            "utf-8"
        )
    ).hexdigest()[:12]

    safe_name = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        project_path.stem
        or "project",
    )

    root = (
        Path(backup_root)
        if backup_root is not None
        else default_project_backup_root()
    )

    return (
        root
        / f"{safe_name}-{key}"
    )


def _atomic_text_write(
    path,
    text,
):
    path = Path(path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(
        path.name
        + ".tmp"
    )
    temporary.write_text(
        text,
        encoding="utf-8",
    )
    temporary.replace(
        path
    )


def _prune_project_backups(
    backup_dir,
    *,
    keep=PROJECT_BACKUP_KEEP,
):
    backup_dir = Path(
        backup_dir
    )
    keep = max(
        1,
        int(keep),
    )

    snapshots = sorted(
        (
            path
            for path in backup_dir.glob(
                "*.json"
            )
            if path.name
            != "latest.json"
        ),
        key=lambda path: (
            path.stat().st_mtime_ns
        ),
        reverse=True,
    )

    for path in snapshots[
        keep:
    ]:
        path.unlink(
            missing_ok=True
        )


def backup_project_snapshot(
    project: Project,
    project_path,
    *,
    backup_root=None,
    now=None,
):
    """
    Store a durable Project snapshot outside the working checkout.

    Every successful project save updates:
      latest.json
    and also writes a timestamped history snapshot.
    """
    project_path = Path(
        project_path
    )
    backup_dir = (
        project_backup_directory(
            project_path,
            backup_root=backup_root,
        )
    )
    backup_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    current_time = (
        now
        if now is not None
        else datetime.now(
            timezone.utc
        )
    )

    if current_time.tzinfo is None:
        current_time = (
            current_time.replace(
                tzinfo=timezone.utc
            )
        )

    timestamp = (
        current_time.astimezone(
            timezone.utc
        ).strftime(
            "%Y%m%dT%H%M%S.%fZ"
        )
    )

    text = _project_json_text(
        project
    )

    snapshot = (
        backup_dir
        / f"{timestamp}.json"
    )
    latest = (
        backup_dir
        / "latest.json"
    )

    _atomic_text_write(
        snapshot,
        text,
    )
    _atomic_text_write(
        latest,
        text,
    )

    metadata = {
        "backup_schema_version": (
            PROJECT_BACKUP_SCHEMA_VERSION
        ),
        "project_path": str(
            project_path.expanduser().resolve(
                strict=False
            )
        ),
        "latest_snapshot": str(
            snapshot
        ),
        "saved_at_utc": timestamp,
    }

    _atomic_text_write(
        backup_dir
        / "metadata.json",
        json.dumps(
            metadata,
            indent=2,
        )
        + "\n",
    )

    _prune_project_backups(
        backup_dir
    )

    return snapshot


def list_project_backups(
    project_path,
    *,
    backup_root=None,
):
    backup_dir = (
        project_backup_directory(
            project_path,
            backup_root=backup_root,
        )
    )

    if not backup_dir.is_dir():
        return []

    return sorted(
        (
            path
            for path in backup_dir.glob(
                "*.json"
            )
            if path.name not in (
                "latest.json",
                "metadata.json",
            )
        ),
        key=lambda path: (
            path.stat().st_mtime_ns
        ),
        reverse=True,
    )


def latest_project_backup(
    project_path,
    *,
    backup_root=None,
):
    backup_dir = (
        project_backup_directory(
            project_path,
            backup_root=backup_root,
        )
    )
    latest = (
        backup_dir
        / "latest.json"
    )

    if latest.is_file():
        return latest

    backups = list_project_backups(
        project_path,
        backup_root=backup_root,
    )

    return (
        backups[0]
        if backups
        else None
    )


def recover_project_backup(
    project_path,
    *,
    backup=None,
    backup_root=None,
):
    project_path = Path(
        project_path
    ).expanduser()

    selected = (
        Path(backup)
        if backup is not None
        else latest_project_backup(
            project_path,
            backup_root=backup_root,
        )
    )

    if (
        selected is None
        or not selected.is_file()
    ):
        raise FileNotFoundError(
            "No PanoPilot project backup is available for "
            f"{project_path}"
        )

    # Validate before restoring.
    recovered = Project.from_dict(
        json.loads(
            selected.read_text(
                encoding="utf-8"
            )
        )
    )

    text = _project_json_text(
        recovered
    )
    _atomic_text_write(
        project_path,
        text,
    )

    # Re-establish a current external snapshot after recovery.
    backup_project_snapshot(
        recovered,
        project_path,
        backup_root=backup_root,
    )

    return {
        "project_path": str(
            project_path
        ),
        "backup": str(
            selected
        ),
        "clip_count": len(
            recovered.clips
        ),
    }


def load_project(path, *, default_aspect="16:9"):
    path = Path(path)
    if not path.exists():
        return Project(output_aspect=default_aspect)
    return Project.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_project(
    project: Project,
    path,
    *,
    create_backup=True,
    backup_root=None,
):
    path = Path(path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    _atomic_text_write(
        path,
        _project_json_text(
            project
        ),
    )

    if create_backup:
        backup_project_snapshot(
            project,
            path,
            backup_root=backup_root,
        )

    return path


def commit_camera_position(
    project: Project,
    source,
    *,
    source_time,
    yaw_deg,
    pitch_deg,
    fov_deg,
    output_aspect=None,
):
    clip = project.clip_for_source(
        source,
        create=True,
    )

    return commit_camera_position_to_clip(
        project,
        clip.id,
        source_time=source_time,
        yaw_deg=yaw_deg,
        pitch_deg=pitch_deg,
        fov_deg=fov_deg,
        output_aspect=output_aspect,
    )
