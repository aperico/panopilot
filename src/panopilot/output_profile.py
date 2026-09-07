"""PanoPilot final conventional-video output policy."""
from __future__ import annotations

from dataclasses import dataclass


OUTPUT_FPS_SELECTIONS = (
    "auto",
    "24",
    "25",
    "30",
    "50",
    "60",
)
DEFAULT_OUTPUT_FPS = "auto"
AUTO_OUTPUT_FPS = 60.0
MAX_DEVICE_FRIENDLY_FPS = 60.0
OUTPUT_RESOLUTIONS = (
    "720p",
    "1080p",
    "1440p",
    "2160p",
)
OUTPUT_QUALITIES = (
    "standard",
    "high",
    "very-high",
    "master",
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
    fps_selection: str
    fps_auto_selected: bool

    def to_dict(self):
        return {
            "aspect": self.aspect,
            "resolution": self.resolution,
            "width": int(self.width),
            "height": int(self.height),
            "fps": float(self.fps),
            "fps_selection": str(self.fps_selection),
            "fps_auto_selected": bool(self.fps_auto_selected),
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
        crf=16,
        preset="slow",
        description="Recommended; stronger detail retention for reframed 360 footage.",
    ),
    "very-high": ExportQualityPreset(
        name="very-high",
        label="Very High",
        crf=13,
        preset="slow",
        description="Near-master H.264 quality with a substantially larger file.",
    ),
    "master": ExportQualityPreset(
        name="master",
        label="Master",
        crf=10,
        preset="slow",
        description="Maximum practical H.264 preservation for archival or later transcodes.",
    ),
}



def resolve_output_fps(selection=DEFAULT_OUTPUT_FPS, *, source_fps=None):
    """
    Resolve one device-friendly final delivery frame rate.

    ``auto`` is the user-facing default. PanoPilot intentionally caps automatic
    delivery at 60 fps because 24/25/30/50/60 are common H.264 delivery rates,
    and 60 fps is the highest common high-frame-rate target used by the current
    supported 100 fps DJI source profile. If a future qualified source profile
    is slower, Auto steps down instead of manufacturing temporal detail.
    """
    selection = str(selection).lower()

    if selection not in OUTPUT_FPS_SELECTIONS:
        raise ValueError(
            "fps must be auto, 24, 25, 30, 50, or 60"
        )

    if selection != "auto":
        return float(selection)

    if source_fps is None:
        return float(AUTO_OUTPUT_FPS)

    source_fps = float(source_fps)
    if source_fps <= 0.0:
        raise ValueError("source_fps must be greater than zero")

    # Highest broadly useful conventional delivery rate not exceeding the
    # qualified source. The current 100 fps DJI profile therefore selects 60.
    for candidate in (60.0, 50.0, 30.0, 25.0, 24.0):
        if source_fps + 0.01 >= candidate:
            return candidate

    # A future very-low-rate source should never be upsampled by Auto.
    return source_fps


def output_fps_label(selection=DEFAULT_OUTPUT_FPS, *, source_fps=None):
    selection = str(selection).lower()
    effective = resolve_output_fps(
        selection,
        source_fps=source_fps,
    )
    if selection == "auto":
        return f"Auto ({effective:.0f} fps recommended)"
    return f"{effective:.0f} fps"

def output_profile_for_aspect(
    aspect,
    resolution=DEFAULT_OUTPUT_RESOLUTION,
    fps=DEFAULT_OUTPUT_FPS,
    *,
    source_fps=None,
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
            "resolution must be '720p', '1080p', '1440p', or '2160p'"
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
        "1440p": (
            2560,
            1440,
        ),
        "2160p": (
            3840,
            2160,
        ),
    }[resolution]

    width, height = landscape

    if aspect == "9:16":
        width, height = (
            height,
            width,
        )

    fps_selection = str(fps).lower()
    effective_fps = resolve_output_fps(
        fps_selection,
        source_fps=source_fps,
    )

    return ProjectOutputProfile(
        aspect=aspect,
        resolution=resolution,
        width=width,
        height=height,
        fps=effective_fps,
        fps_selection=fps_selection,
        fps_auto_selected=(fps_selection == "auto"),
    )


def output_profile_for_project(
    project,
    *,
    resolution=None,
    fps=None,
    source_fps=None,
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
    selected_fps = (
        getattr(
            project,
            "output_fps",
            DEFAULT_OUTPUT_FPS,
        )
        if fps is None
        else str(fps)
    )
    return output_profile_for_aspect(
        project.output_aspect,
        selected,
        selected_fps,
        source_fps=source_fps,
    )


def export_quality_for_name(name):
    name = str(name).lower()

    try:
        return _QUALITY_PRESETS[name]
    except KeyError as exc:
        raise ValueError(
            "quality must be 'standard', 'high', 'very-high', or 'master'"
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
