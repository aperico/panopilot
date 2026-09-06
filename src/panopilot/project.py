"""
Minimal non-destructive PanoPilot project model for Iteration 1.

0.12 introduces only the persistence needed to prove the critical UX boundary:

    Explore freely
        ↓
    explicit "Use this view"
        ↓
    persisted Camera Position

Exploratory camera movement never mutates this model.

The current JSON representation is an internal prototype format. It is not yet
declared a stable public interchange format.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Optional


SCHEMA_VERSION = 1
TIME_MATCH_TOLERANCE_S = 1e-6


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

    def sort_positions(self):
        self.camera_positions.sort(key=lambda position: position.source_time)

    def position_at(self, source_time: float) -> Optional[CameraPosition]:
        target = float(source_time)

        for position in self.camera_positions:
            if abs(position.source_time - target) <= TIME_MATCH_TOLERANCE_S:
                return position

        return None

    def upsert_camera_position(
        self,
        source_time: float,
        yaw_deg: float,
        pitch_deg: float,
        fov_deg: float,
    ):
        """
        Create or update the Camera Position at this source-media moment.

        This is intentionally an upsert: repeatedly choosing "Use this view" at
        the same moment updates that committed view instead of creating
        ambiguous duplicate keyframes.
        """
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
            "camera_positions": [
                position.to_dict()
                for position in self.camera_positions
            ],
        }

    @classmethod
    def from_dict(cls, data):
        clip = cls(
            id=str(data["id"]),
            source=str(data["source"]),
            camera_positions=[
                CameraPosition.from_dict(position)
                for position in data.get("camera_positions", [])
            ],
        )
        clip.sort_positions()
        return clip


@dataclass
class Project:
    output_aspect: str = "16:9"
    clips: list[Clip] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        if self.output_aspect not in ("16:9", "9:16"):
            raise ValueError("output_aspect must be '16:9' or '9:16'")

    def clip_for_source(self, source, *, create=False):
        source = str(source)

        for clip in self.clips:
            if clip.source == source:
                return clip

        if not create:
            return None

        clip = Clip(
            id=f"clip-{len(self.clips) + 1}",
            source=source,
        )
        self.clips.append(clip)
        return clip

    def to_dict(self):
        return {
            "schema_version": int(self.schema_version),
            "output_frame": {
                "aspect": self.output_aspect,
            },
            "clips": [
                clip.to_dict()
                for clip in self.clips
            ],
        }

    @classmethod
    def from_dict(cls, data):
        version = int(data.get("schema_version", 0))

        if version != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported project schema_version {version}; "
                f"expected {SCHEMA_VERSION}"
            )

        output_frame = data.get("output_frame", {})
        project = cls(
            output_aspect=str(output_frame.get("aspect", "16:9")),
            clips=[
                Clip.from_dict(clip)
                for clip in data.get("clips", [])
            ],
            schema_version=version,
        )

        return project


def load_project(path, *, default_aspect="16:9"):
    path = Path(path)

    if not path.exists():
        return Project(output_aspect=default_aspect)

    return Project.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )


def save_project(project: Project, path):
    """
    Atomically persist the project.

    Source recordings are never modified.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_name(path.name + ".tmp")

    temporary.write_text(
        json.dumps(project.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )

    temporary.replace(path)

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
    clip = project.clip_for_source(source, create=True)

    position, created = clip.upsert_camera_position(
        source_time=source_time,
        yaw_deg=yaw_deg,
        pitch_deg=pitch_deg,
        fov_deg=fov_deg,
    )

    if output_aspect is not None:
        if output_aspect not in ("16:9", "9:16"):
            raise ValueError("output_aspect must be '16:9' or '9:16'")
        project.output_aspect = output_aspect

    index = clip.camera_positions.index(position)

    return {
        "created": bool(created),
        "clip_id": clip.id,
        "position_index": index,
        "position_number": index + 1,
        "camera_position": position.to_dict(),
    }
