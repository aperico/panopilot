"""
PanoPilot Iteration-1 quantitative acceptance harness.

The product requirements deliberately separate implementation from measurable
acceptance. This module resolves the remaining quantitative constants and
provides one repeatable command that can be executed on the Fedora reference
system with the real Project sources.

The report is evidence, not a benchmark marketing score. It records:
- supported OSV profile conformance;
- preview/final Virtual Camera geometry equivalence;
- ready-preview camera-manipulation latency;
- random scrub-to-visible-frame latency;
- cached-preview A/V stream timing alignment;
- reference-system qualification.

The two latency requirements are considered field-qualified only when the
report is produced on the designated Fedora / AMD Radeon 890M reference
machine.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import time

import cv2
import numpy as np

from .cache import (
    PanoramaCacheReader,
    PreviewProfile,
    ensure_preview_cache,
)
from .output_profile import (
    output_profile_for_aspect,
)
from .project import (
    assert_project_sources,
    load_project,
)
from .source import (
    audio_streams,
    probe_source,
)
from .source_validation import (
    SUPPORTED_OSV_PROFILE_ID,
    validate_source_recording,
)
from .virtual_camera import (
    RectilinearProjector,
    VirtualCamera,
    equirectangular_map,
    reframe_equirectangular,
)


ACCEPTANCE_SCHEMA_VERSION = 1

# Resolved Iteration-1 quantitative targets.
CAMERA_EQUIVALENCE_MAX_SOURCE_PIXEL = 0.05
CAMERA_RESPONSE_P95_MS = 100.0
SCRUB_RESPONSE_P95_MS = 250.0
PREVIEW_AV_SYNC_MAX_MS = 100.0

REFERENCE_OS_ID = "fedora"
REFERENCE_GPU_TOKENS = (
    "radeon 890m",
    "strix",
)


@dataclass(frozen=True)
class AcceptanceRequirement:
    requirement_id: str
    passed: bool
    measured: dict
    threshold: dict
    evidence: str

    def to_dict(self):
        return {
            "requirement_id": self.requirement_id,
            "passed": bool(
                self.passed
            ),
            "measured": dict(
                self.measured
            ),
            "threshold": dict(
                self.threshold
            ),
            "evidence": str(
                self.evidence
            ),
        }


def _percentile(values, percentile):
    values = np.asarray(
        values,
        dtype=np.float64,
    )

    if values.size == 0:
        return None

    return float(
        np.percentile(
            values,
            float(
                percentile
            ),
        )
    )


def _parse_os_release():
    result = {}

    try:
        for raw in Path(
            "/etc/os-release"
        ).read_text(
            encoding="utf-8"
        ).splitlines():
            if (
                "=" not in raw
                or raw.startswith(
                    "#"
                )
            ):
                continue

            key, value = raw.split(
                "=",
                1,
            )
            result[
                key.lower()
            ] = value.strip().strip(
                '"'
            )
    except OSError:
        pass

    return result


def _command_text(command):
    try:
        completed = subprocess.run(
            list(
                command
            ),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (
        OSError,
        subprocess.TimeoutExpired,
    ):
        return ""

    return (
        completed.stdout
        + "\n"
        + completed.stderr
    ).strip()


def detect_reference_system():
    os_release = _parse_os_release()
    lspci = _command_text(
        (
            "lspci",
            "-nn",
        )
    )
    vainfo = _command_text(
        (
            "vainfo",
        )
    )
    graphics_text = (
        lspci
        + "\n"
        + vainfo
    ).lower()

    os_id = str(
        os_release.get(
            "id",
            "",
        )
    ).lower()

    gpu_match = any(
        token
        in graphics_text
        for token in REFERENCE_GPU_TOKENS
    )
    os_match = (
        os_id
        == REFERENCE_OS_ID
    )

    return {
        "qualified": bool(
            os_match
            and gpu_match
        ),
        "os_match": bool(
            os_match
        ),
        "gpu_match": bool(
            gpu_match
        ),
        "os_id": os_id,
        "os_version": os_release.get(
            "version_id"
        ),
        "os_pretty_name": os_release.get(
            "pretty_name"
        ),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "gpu_detection_tokens": list(
            REFERENCE_GPU_TOKENS
        ),
        "lspci_excerpt": "\n".join(
            line
            for line in lspci.splitlines()
            if any(
                word
                in line.lower()
                for word in (
                    "vga",
                    "display",
                    "3d controller",
                    "amd",
                    "ati",
                )
            )
        )[
            :2000
        ],
    }


def camera_equivalence_metrics():
    """
    Compare the Preview reference map with the optimized final-render map.

    Geometric equivalence is measured in source panorama pixels, with
    seam-aware horizontal distance.
    """
    panorama_width = 3840
    panorama_height = 1920
    cameras = (
        VirtualCamera(
            yaw_deg=0.0,
            pitch_deg=0.0,
            roll_deg=0.0,
            fov_deg=90.0,
        ),
        VirtualCamera(
            yaw_deg=43.25,
            pitch_deg=-18.5,
            roll_deg=12.75,
            fov_deg=72.0,
        ),
        VirtualCamera(
            yaw_deg=-151.0,
            pitch_deg=37.0,
            roll_deg=-31.0,
            fov_deg=112.0,
        ),
    )

    observations = []
    global_max = 0.0

    for aspect in (
        "16:9",
        "9:16",
    ):
        for resolution in (
            "720p",
            "1080p",
        ):
            profile = output_profile_for_aspect(
                aspect,
                resolution,
            )
            projector = RectilinearProjector(
                panorama_width,
                panorama_height,
                profile.width,
                profile.height,
            )

            for camera in cameras:
                reference_x, reference_y = (
                    equirectangular_map(
                        panorama_width,
                        panorama_height,
                        profile.width,
                        profile.height,
                        camera,
                    )
                )
                optimized_x, optimized_y = (
                    projector.map(
                        camera
                    )
                )

                dx = np.abs(
                    reference_x
                    - optimized_x
                ).astype(
                    np.float64
                )
                dx = np.minimum(
                    dx,
                    float(
                        panorama_width
                    )
                    - dx,
                )
                dy = np.abs(
                    reference_y
                    - optimized_y
                ).astype(
                    np.float64
                )

                maximum = max(
                    float(
                        np.max(
                            dx
                        )
                    ),
                    float(
                        np.max(
                            dy
                        )
                    ),
                )
                global_max = max(
                    global_max,
                    maximum,
                )

                observations.append(
                    {
                        "aspect": aspect,
                        "resolution": resolution,
                        "yaw_deg": float(
                            camera.yaw_deg
                        ),
                        "pitch_deg": float(
                            camera.pitch_deg
                        ),
                        "roll_deg": float(
                            camera.roll_deg
                        ),
                        "fov_deg": float(
                            camera.fov_deg
                        ),
                        "max_source_pixel_error": float(
                            maximum
                        ),
                        "p99_9_source_pixel_error": float(
                            max(
                                np.percentile(
                                    dx,
                                    99.9,
                                ),
                                np.percentile(
                                    dy,
                                    99.9,
                                ),
                            )
                        ),
                    }
                )

    return {
        "max_source_pixel_error": float(
            global_max
        ),
        "threshold_source_pixels": float(
            CAMERA_EQUIVALENCE_MAX_SOURCE_PIXEL
        ),
        "passed": bool(
            global_max
            <= CAMERA_EQUIVALENCE_MAX_SOURCE_PIXEL
        ),
        "observations": observations,
    }


def _stream_duration_seconds(
    stream,
):
    value = stream.get(
        "duration"
    )

    if value not in (
        None,
        "",
        "N/A",
    ):
        try:
            duration = float(
                value
            )

            if (
                math.isfinite(
                    duration
                )
                and duration >= 0.0
            ):
                return duration
        except (
            TypeError,
            ValueError,
        ):
            pass

    duration_ts = stream.get(
        "duration_ts"
    )
    time_base = stream.get(
        "time_base"
    )

    if (
        duration_ts in (
            None,
            "",
            "N/A",
        )
        or time_base in (
            None,
            "",
            "N/A",
            "0/0",
        )
    ):
        return None

    try:
        return float(
            int(
                duration_ts
            )
            * Fraction(
                str(
                    time_base
                )
            )
        )
    except (
        TypeError,
        ValueError,
        ZeroDivisionError,
    ):
        return None


def _stream_start_seconds(
    stream,
):
    value = stream.get(
        "start_time"
    )

    if value in (
        None,
        "",
        "N/A",
    ):
        return 0.0

    try:
        start = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0.0

    return (
        start
        if math.isfinite(
            start
        )
        else 0.0
    )


def preview_av_sync_metrics(
    preview_path,
):
    probe = probe_source(
        preview_path
    )
    videos = [
        stream
        for stream in probe.get(
            "streams",
            []
        )
        if (
            stream.get(
                "codec_type"
            )
            == "video"
            and not stream.get(
                "disposition",
                {},
            ).get(
                "attached_pic"
            )
        )
    ]
    audios = audio_streams(
        probe
    )

    if not videos:
        raise RuntimeError(
            "Preview cache contains no video stream"
        )

    if not audios:
        return {
            "applicable": False,
            "passed": True,
            "reason": "preview has no audio stream",
            "max_error_ms": 0.0,
            "threshold_ms": float(
                PREVIEW_AV_SYNC_MAX_MS
            ),
        }

    video = videos[
        0
    ]
    audio = audios[
        0
    ]
    video_start = (
        _stream_start_seconds(
            video
        )
    )
    audio_start = (
        _stream_start_seconds(
            audio
        )
    )
    video_duration = (
        _stream_duration_seconds(
            video
        )
    )
    audio_duration = (
        _stream_duration_seconds(
            audio
        )
    )

    if (
        video_duration is None
        or audio_duration is None
    ):
        raise RuntimeError(
            "Preview A/V stream durations are unavailable"
        )

    video_end = (
        video_start
        + video_duration
    )
    audio_end = (
        audio_start
        + audio_duration
    )
    start_error_ms = (
        abs(
            video_start
            - audio_start
        )
        * 1000.0
    )
    end_error_ms = (
        abs(
            video_end
            - audio_end
        )
        * 1000.0
    )
    maximum = max(
        start_error_ms,
        end_error_ms,
    )

    return {
        "applicable": True,
        "passed": bool(
            maximum
            <= PREVIEW_AV_SYNC_MAX_MS
        ),
        "video_start_s": float(
            video_start
        ),
        "audio_start_s": float(
            audio_start
        ),
        "video_duration_s": float(
            video_duration
        ),
        "audio_duration_s": float(
            audio_duration
        ),
        "start_error_ms": float(
            start_error_ms
        ),
        "end_error_ms": float(
            end_error_ms
        ),
        "max_error_ms": float(
            maximum
        ),
        "threshold_ms": float(
            PREVIEW_AV_SYNC_MAX_MS
        ),
    }


def _view_dimensions(
    aspect,
    long_edge=800,
):
    long_edge = int(
        long_edge
    )

    if aspect == "16:9":
        return (
            long_edge,
            int(
                round(
                    long_edge
                    * 9.0
                    / 16.0
                )
            ),
        )

    return (
        int(
            round(
                long_edge
                * 9.0
                / 16.0
            )
        ),
        long_edge,
    )


def benchmark_camera_response(
    entry,
    *,
    aspect,
    sample_count=24,
):
    width, height = _view_dimensions(
        aspect,
        800,
    )

    with PanoramaCacheReader(
        entry
    ) as reader:
        source_time = min(
            max(
                0.0,
                (
                    entry.source_duration
                    or reader.media_duration
                )
                * 0.45,
            ),
            max(
                0.0,
                reader.media_duration
                - 1.0
                / reader.fps,
            ),
        )
        panorama, _actual, _index = (
            reader.read_at(
                source_time
            )
        )

    cameras = (
        VirtualCamera(
            yaw_deg=0.0,
            pitch_deg=0.0,
            roll_deg=0.0,
            fov_deg=90.0,
        ),
        VirtualCamera(
            yaw_deg=4.0,
            pitch_deg=-2.0,
            roll_deg=1.0,
            fov_deg=88.0,
        ),
        VirtualCamera(
            yaw_deg=-11.0,
            pitch_deg=6.0,
            roll_deg=-3.0,
            fov_deg=82.0,
        ),
        VirtualCamera(
            yaw_deg=27.0,
            pitch_deg=-12.0,
            roll_deg=8.0,
            fov_deg=100.0,
        ),
    )

    # Warm the OpenCV and allocation paths before timing visible interaction.
    for camera in cameras:
        reframe_equirectangular(
            panorama,
            camera,
            width,
            height,
        )

    timings = []

    for index in range(
        int(
            sample_count
        )
    ):
        camera = cameras[
            index
            % len(
                cameras
            )
        ]
        started = time.perf_counter()
        reframe_equirectangular(
            panorama,
            camera,
            width,
            height,
        )
        timings.append(
            (
                time.perf_counter()
                - started
            )
            * 1000.0
        )

    p95 = _percentile(
        timings,
        95,
    )

    return {
        "sample_count": len(
            timings
        ),
        "view_width": int(
            width
        ),
        "view_height": int(
            height
        ),
        "median_ms": _percentile(
            timings,
            50,
        ),
        "p95_ms": p95,
        "max_ms": max(
            timings
        ),
        "threshold_p95_ms": float(
            CAMERA_RESPONSE_P95_MS
        ),
        "passed": bool(
            p95 is not None
            and p95
            <= CAMERA_RESPONSE_P95_MS
        ),
    }


def benchmark_scrub_response(
    entry,
    *,
    aspect,
):
    width, height = _view_dimensions(
        aspect,
        800,
    )
    fractions = (
        0.07,
        0.82,
        0.21,
        0.64,
        0.36,
        0.93,
        0.12,
        0.55,
        0.76,
        0.29,
        0.88,
        0.45,
    )
    camera = VirtualCamera(
        yaw_deg=17.0,
        pitch_deg=-6.0,
        roll_deg=4.0,
        fov_deg=86.0,
    )
    timings = []

    with PanoramaCacheReader(
        entry
    ) as reader:
        duration = min(
            (
                entry.source_duration
                or reader.media_duration
            ),
            reader.media_duration,
        )
        duration = max(
            duration,
            1.0
            / reader.fps,
        )

        # Warm one sequential decode/render before random seeking.
        frame, _actual, _index = (
            reader.read_at(
                0.0
            )
        )
        reframe_equirectangular(
            frame,
            camera,
            width,
            height,
        )

        for fraction in fractions:
            source_time = min(
                max(
                    0.0,
                    duration
                    * fraction,
                ),
                max(
                    0.0,
                    duration
                    - 1.0
                    / reader.fps,
                ),
            )
            started = (
                time.perf_counter()
            )
            frame, _actual, _index = (
                reader.read_at(
                    source_time
                )
            )
            reframe_equirectangular(
                frame,
                camera,
                width,
                height,
            )
            timings.append(
                (
                    time.perf_counter()
                    - started
                )
                * 1000.0
            )

    p95 = _percentile(
        timings,
        95,
    )

    return {
        "sample_count": len(
            timings
        ),
        "view_width": int(
            width
        ),
        "view_height": int(
            height
        ),
        "median_ms": _percentile(
            timings,
            50,
        ),
        "p95_ms": p95,
        "max_ms": max(
            timings
        ),
        "threshold_p95_ms": float(
            SCRUB_RESPONSE_P95_MS
        ),
        "passed": bool(
            p95 is not None
            and p95
            <= SCRUB_RESPONSE_P95_MS
        ),
    }


def _preview_profile_for_project(
    project,
):
    return PreviewProfile(
        width=1280,
        height=640,
        fps=20.0,
        with_audio=True,
        stabilization_amount=float(
            project.stabilization_amount
        ),
    )


def _emit(
    progress_callback,
    message,
):
    if progress_callback is not None:
        progress_callback(
            str(
                message
            )
        )


def run_iteration1_acceptance(
    project_path,
    *,
    report_path=None,
    cache_dir=None,
    rebuild_preview=False,
    progress_callback=None,
):
    project_path = Path(
        project_path
    )
    project = load_project(
        project_path
    )

    if not project.clips:
        raise ValueError(
            "Acceptance requires a Project with at least one Clip"
        )

    assert_project_sources(
        project
    )

    _emit(
        progress_callback,
        "Checking reference system",
    )
    reference_system = (
        detect_reference_system()
    )

    _emit(
        progress_callback,
        "Validating supported DJI OSV profile",
    )
    source_results = []
    source_pass = True

    for clip in project.clips:
        acceptance = (
            validate_source_recording(
                clip.source,
                decode_smoke=True,
            )
        )
        source_results.append(
            {
                "clip_id": clip.id,
                **acceptance.to_dict(),
            }
        )
        source_pass = (
            source_pass
            and acceptance.accepted
            and acceptance.profile_id
            == SUPPORTED_OSV_PROFILE_ID
        )

    _emit(
        progress_callback,
        "Measuring preview/final camera geometry equivalence",
    )
    camera_equivalence = (
        camera_equivalence_metrics()
    )

    profile = (
        _preview_profile_for_project(
            project
        )
    )
    entries = []

    for index, clip in enumerate(
        project.clips,
        start=1,
    ):
        _emit(
            progress_callback,
            (
                "Preparing/reusing acceptance preview "
                f"{index}/{len(project.clips)} — "
                f"{Path(clip.source).name}"
            ),
        )
        entry = ensure_preview_cache(
            clip.source,
            profile=profile,
            cache_dir=cache_dir,
            rebuild=(
                rebuild_preview
            ),
        )
        entries.append(
            (
                clip,
                entry,
            )
        )

    _emit(
        progress_callback,
        "Measuring preview A/V alignment",
    )
    av_results = []
    av_pass = True

    for clip, entry in entries:
        metrics = (
            preview_av_sync_metrics(
                entry.video_path
            )
        )
        av_results.append(
            {
                "clip_id": clip.id,
                "source": clip.source,
                "preview": str(
                    entry.video_path
                ),
                **metrics,
            }
        )
        av_pass = (
            av_pass
            and bool(
                metrics[
                    "passed"
                ]
            )
        )

    _emit(
        progress_callback,
        "Benchmarking ready-preview camera response",
    )
    camera_latency_results = []
    camera_latency_pass = True

    for clip, entry in entries:
        metrics = benchmark_camera_response(
            entry,
            aspect=(
                project.output_aspect
            ),
        )
        camera_latency_results.append(
            {
                "clip_id": clip.id,
                "source": clip.source,
                **metrics,
            }
        )
        camera_latency_pass = (
            camera_latency_pass
            and bool(
                metrics[
                    "passed"
                ]
            )
        )

    _emit(
        progress_callback,
        "Benchmarking random scrub response",
    )
    scrub_results = []
    scrub_pass = True

    for clip, entry in entries:
        metrics = benchmark_scrub_response(
            entry,
            aspect=(
                project.output_aspect
            ),
        )
        scrub_results.append(
            {
                "clip_id": clip.id,
                "source": clip.source,
                **metrics,
            }
        )
        scrub_pass = (
            scrub_pass
            and bool(
                metrics[
                    "passed"
                ]
            )
        )

    requirements = {
        "SYS-MEDIA-001": AcceptanceRequirement(
            requirement_id=(
                "SYS-MEDIA-001"
            ),
            passed=source_pass,
            measured={
                "profile_id": (
                    SUPPORTED_OSV_PROFILE_ID
                ),
                "clip_results": (
                    source_results
                ),
            },
            threshold={
                "supported_profile_id": (
                    SUPPORTED_OSV_PROFILE_ID
                ),
            },
            evidence=(
                "source profile + calibration + orientation + decode smoke"
            ),
        ).to_dict(),
        "SYS-CAM-009": AcceptanceRequirement(
            requirement_id=(
                "SYS-CAM-009"
            ),
            passed=bool(
                camera_equivalence[
                    "passed"
                ]
            ),
            measured=(
                camera_equivalence
            ),
            threshold={
                "max_source_pixel_error": float(
                    CAMERA_EQUIVALENCE_MAX_SOURCE_PIXEL
                ),
            },
            evidence=(
                "reference preview map versus optimized final projector map"
            ),
        ).to_dict(),
        "SYS-AUDIO-003": AcceptanceRequirement(
            requirement_id=(
                "SYS-AUDIO-003"
            ),
            passed=av_pass,
            measured={
                "clip_results": (
                    av_results
                ),
            },
            threshold={
                "max_preview_av_sync_error_ms": float(
                    PREVIEW_AV_SYNC_MAX_MS
                ),
            },
            evidence=(
                "cached preview audio/video start and end timing"
            ),
        ).to_dict(),
        "SYS-PERF-001": AcceptanceRequirement(
            requirement_id=(
                "SYS-PERF-001"
            ),
            passed=(
                camera_latency_pass
                and bool(
                    reference_system[
                        "qualified"
                    ]
                )
            ),
            measured={
                "reference_system_qualified": bool(
                    reference_system[
                        "qualified"
                    ]
                ),
                "clip_results": (
                    camera_latency_results
                ),
            },
            threshold={
                "p95_ms": float(
                    CAMERA_RESPONSE_P95_MS
                ),
                "reference_system_required": True,
            },
            evidence=(
                "ready cached panorama -> 800px-long-edge visible reframe"
            ),
        ).to_dict(),
        "SYS-PERF-002": AcceptanceRequirement(
            requirement_id=(
                "SYS-PERF-002"
            ),
            passed=(
                scrub_pass
                and bool(
                    reference_system[
                        "qualified"
                    ]
                )
            ),
            measured={
                "reference_system_qualified": bool(
                    reference_system[
                        "qualified"
                    ]
                ),
                "clip_results": (
                    scrub_results
                ),
            },
            threshold={
                "p95_ms": float(
                    SCRUB_RESPONSE_P95_MS
                ),
                "reference_system_required": True,
            },
            evidence=(
                "random preview-cache seek + 800px-long-edge reframe"
            ),
        ).to_dict(),
    }

    all_requirement_pass = all(
        item[
            "passed"
        ]
        for item in requirements.values()
    )

    result = {
        "acceptance_schema_version": (
            ACCEPTANCE_SCHEMA_VERSION
        ),
        "project": str(
            project_path
        ),
        "reference_system": (
            reference_system
        ),
        "thresholds": {
            "SUPPORTED-OSV-PROFILE-001": (
                SUPPORTED_OSV_PROFILE_ID
            ),
            "CAMERA-EQUIVALENCE-001_source_pixels": float(
                CAMERA_EQUIVALENCE_MAX_SOURCE_PIXEL
            ),
            "CAMERA-RESPONSE-001_p95_ms": float(
                CAMERA_RESPONSE_P95_MS
            ),
            "SCRUB-RESPONSE-001_p95_ms": float(
                SCRUB_RESPONSE_P95_MS
            ),
            "PREVIEW-AV-SYNC-001_ms": float(
                PREVIEW_AV_SYNC_MAX_MS
            ),
        },
        "requirements": requirements,
        "all_five_pass": bool(
            all_requirement_pass
        ),
        "iteration1_acceptance_qualified": bool(
            all_requirement_pass
            and reference_system[
                "qualified"
            ]
        ),
    }

    if report_path is not None:
        report_path = Path(
            report_path
        )
        report_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        temporary = report_path.with_suffix(
            report_path.suffix
            + ".tmp"
        )
        temporary.write_text(
            json.dumps(
                result,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(
            report_path
        )
        result[
            "report_path"
        ] = str(
            report_path
        )

    return result


def format_acceptance_summary(
    result,
):
    lines = [
        "PanoPilot Iteration-1 Acceptance",
        (
            "Reference system: "
            + (
                "QUALIFIED"
                if result[
                    "reference_system"
                ][
                    "qualified"
                ]
                else "NOT QUALIFIED"
            )
        ),
    ]

    for requirement_id in (
        "SYS-MEDIA-001",
        "SYS-CAM-009",
        "SYS-AUDIO-003",
        "SYS-PERF-001",
        "SYS-PERF-002",
    ):
        item = result[
            "requirements"
        ][
            requirement_id
        ]
        lines.append(
            f"{requirement_id}: "
            + (
                "PASS"
                if item[
                    "passed"
                ]
                else "FAIL / NOT QUALIFIED"
            )
        )

    lines.append(
        "Iteration-1 acceptance: "
        + (
            "PASS"
            if result[
                "iteration1_acceptance_qualified"
            ]
            else "PENDING / FAIL"
        )
    )

    return "\n".join(
        lines
    )
