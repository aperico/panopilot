"""Iteration-1 Project Output Profile policy."""
from __future__ import annotations

from dataclasses import dataclass


ITERATION_1_OUTPUT_FPS = 30.0


@dataclass(frozen=True)
class ProjectOutputProfile:
    aspect: str
    width: int
    height: int
    fps: float

    def to_dict(self):
        return {
            "aspect": self.aspect,
            "width": int(self.width),
            "height": int(self.height),
            "fps": float(self.fps),
        }


def output_profile_for_aspect(aspect):
    """
    Resolve OUTPUT-PROFILE-001 for Iteration 1.

    Resolution/FPS are automatic policy derived from the saved Project aspect,
    so existing Project schema v3 remains sufficient to reproduce the complete
    Iteration-1 Output Profile.
    """
    aspect = str(aspect)

    if aspect == "16:9":
        return ProjectOutputProfile(
            aspect="16:9",
            width=1920,
            height=1080,
            fps=ITERATION_1_OUTPUT_FPS,
        )

    if aspect == "9:16":
        return ProjectOutputProfile(
            aspect="9:16",
            width=1080,
            height=1920,
            fps=ITERATION_1_OUTPUT_FPS,
        )

    raise ValueError(
        "aspect must be '16:9' or '9:16'"
    )


def output_profile_for_project(project):
    return output_profile_for_aspect(
        project.output_aspect
    )
