"""PanoPilot final conventional-video output policy."""
from __future__ import annotations

from dataclasses import dataclass


OUTPUT_FPS = 30.0
OUTPUT_RESOLUTIONS = (
    "720p",
    "1080p",
)
OUTPUT_QUALITIES = (
    "standard",
    "high",
    "very-high",
)
DEFAULT_OUTPUT_RESOLUTION = "1080p"
DEFAULT_OUTPUT_QUALITY = "high"


@dataclass(frozen=True)
class ProjectOutputProfile:
    aspect: str
    resolution: str
    width: int
    height: int
    fps: float

    def to_dict(self):
        return {
            "aspect": self.aspect,
            "resolution": self.resolution,
            "width": int(self.width),
            "height": int(self.height),
            "fps": float(self.fps),
        }


@dataclass(frozen=True)
class ExportQualityPreset:
    name: str
    label: str
    crf: int
    preset: str
    description: str

    def to_dict(self):
        return {
            "name": self.name,
            "label": self.label,
            "crf": int(self.crf),
            "preset": self.preset,
            "description": self.description,
        }


_QUALITY_PRESETS = {
    "standard": ExportQualityPreset(
        name="standard",
        label="Standard",
        crf=23,
        preset="medium",
        description="Smaller file; good general sharing quality.",
    ),
    "high": ExportQualityPreset(
        name="high",
        label="High",
        crf=18,
        preset="medium",
        description="Recommended; preserves the previous PanoPilot export quality.",
    ),
    "very-high": ExportQualityPreset(
        name="very-high",
        label="Very High",
        crf=15,
        preset="medium",
        description="Higher fidelity with a larger H.264 file.",
    ),
}


def output_profile_for_aspect(
    aspect,
    resolution=DEFAULT_OUTPUT_RESOLUTION,
):
    """Resolve the saved final-video geometry for one aspect/resolution pair."""
    aspect = str(aspect)
    resolution = str(resolution).lower()

    if aspect not in (
        "16:9",
        "9:16",
    ):
        raise ValueError(
            "aspect must be '16:9' or '9:16'"
        )

    if resolution not in OUTPUT_RESOLUTIONS:
        raise ValueError(
            "resolution must be '720p' or '1080p'"
        )

    landscape = {
        "720p": (
            1280,
            720,
        ),
        "1080p": (
            1920,
            1080,
        ),
    }[resolution]

    width, height = landscape

    if aspect == "9:16":
        width, height = (
            height,
            width,
        )

    return ProjectOutputProfile(
        aspect=aspect,
        resolution=resolution,
        width=width,
        height=height,
        fps=OUTPUT_FPS,
    )


def output_profile_for_project(
    project,
    *,
    resolution=None,
):
    selected = (
        getattr(
            project,
            "output_resolution",
            DEFAULT_OUTPUT_RESOLUTION,
        )
        if resolution is None
        else str(resolution)
    )
    return output_profile_for_aspect(
        project.output_aspect,
        selected,
    )


def export_quality_for_name(name):
    name = str(name).lower()

    try:
        return _QUALITY_PRESETS[name]
    except KeyError as exc:
        raise ValueError(
            "quality must be 'standard', 'high', or 'very-high'"
        ) from exc


def export_quality_for_project(
    project,
    *,
    quality=None,
):
    selected = (
        getattr(
            project,
            "output_quality",
            DEFAULT_OUTPUT_QUALITY,
        )
        if quality is None
        else str(quality)
    )
    return export_quality_for_name(
        selected
    )
