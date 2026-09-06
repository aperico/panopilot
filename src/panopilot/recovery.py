"""Project reconstruction aids for lost PanoPilot Project JSON files."""
from __future__ import annotations

from pathlib import Path

from .cache import (
    discover_cached_sources,
)
from .project import (
    Clip,
    Project,
    save_project,
)


def parse_candidate_indexes(
    text,
    *,
    candidate_count,
):
    """
    Parse 1-based comma/space separated indexes while preserving user order.
    """
    raw = str(text).replace(
        ",",
        " ",
    )
    values = []

    for token in raw.split():
        try:
            value = int(
                token
            )
        except ValueError as exc:
            raise ValueError(
                f"Invalid source number: {token}"
            ) from exc

        if not (
            1
            <= value
            <= int(
                candidate_count
            )
        ):
            raise ValueError(
                "Source number out of range: "
                f"{value} (valid 1..{candidate_count})"
            )

        if value in values:
            raise ValueError(
                f"Duplicate source number: {value}"
            )

        values.append(
            value
        )

    if not values:
        raise ValueError(
            "Select at least one source"
        )

    return values


def rebuild_project_from_cache(
    project_path,
    *,
    indexes,
    cache_dir=None,
    output_aspect="16:9",
    camera_motion_easing="smooth",
    camera_motion_strength=1.0,
):
    """
    Create a fresh Project shell from selected source recordings discovered in
    preview-cache metadata.

    Recoverable:
      - original source paths
      - source durations (diagnostic only)

    Not recoverable from preview cache:
      - prior Clip order unless user supplies it
      - trims
      - Camera Positions
      - prior Camera Motion settings

    The user-selected ``indexes`` establish Clip order explicitly.
    """
    project_path = Path(
        project_path
    )
    candidates = (
        discover_cached_sources(
            cache_dir=cache_dir,
            existing_only=True,
        )
    )

    if not candidates:
        raise RuntimeError(
            "No existing source recordings were found in the "
            "PanoPilot preview cache."
        )

    selected = []

    for index in indexes:
        zero_index = (
            int(index)
            - 1
        )

        if not (
            0
            <= zero_index
            < len(candidates)
        ):
            raise ValueError(
                f"Source number out of range: {index}"
            )

        selected.append(
            candidates[
                zero_index
            ]
        )

    project = Project(
        output_aspect=output_aspect,
        camera_motion_easing=(
            camera_motion_easing
        ),
        camera_motion_strength=float(
            camera_motion_strength
        ),
        clips=[
            Clip(
                id=f"clip-{number}",
                source=str(
                    candidate.source.resolve()
                ),
            )
            for number, candidate
            in enumerate(
                selected,
                start=1,
            )
        ],
    )

    save_project(
        project,
        project_path,
    )

    return {
        "project": str(
            project_path
        ),
        "clip_count": len(
            project.clips
        ),
        "clips": [
            {
                "id": clip.id,
                "source": clip.source,
            }
            for clip in project.clips
        ],
        "output_aspect": (
            project.output_aspect
        ),
        "camera_motion": {
            "easing": (
                project.camera_motion_easing
            ),
            "strength": float(
                project.camera_motion_strength
            ),
        },
    }
