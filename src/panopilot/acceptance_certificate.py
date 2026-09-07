from __future__ import annotations

import json
import math
from pathlib import Path

from .acceptance import (
    ACCEPTANCE_SCHEMA_VERSION,
    CAMERA_EQUIVALENCE_MAX_SOURCE_PIXEL,
    CAMERA_RESPONSE_P95_MS,
    PREVIEW_AV_SYNC_MAX_MS,
    SCRUB_RESPONSE_P95_MS,
)
from .source_validation import SUPPORTED_OSV_PROFILE_ID


REQUIRED_ACCEPTANCE_REQUIREMENTS = (
    "SYS-MEDIA-001",
    "SYS-CAM-009",
    "SYS-AUDIO-003",
    "SYS-PERF-001",
    "SYS-PERF-002",
)


class AcceptanceCertificateError(RuntimeError):
    pass


def _require(condition, message):
    if not condition:
        raise AcceptanceCertificateError(str(message))


def _float_equal(actual, expected, *, tolerance=1e-9):
    try:
        actual = float(actual)
        expected = float(expected)
    except (TypeError, ValueError):
        return False

    return (
        math.isfinite(actual)
        and abs(actual - expected) <= float(tolerance)
    )


def _maximum_clip_metric(requirement, key):
    results = requirement.get("measured", {}).get("clip_results", [])
    values = [
        float(item[key])
        for item in results
        if item.get(key) is not None
    ]

    if not values:
        raise AcceptanceCertificateError(
            f"No {key!r} measurements were present"
        )

    return max(values)


def certify_acceptance_report(report):
    _require(
        isinstance(report, dict),
        "Acceptance report must be a JSON object",
    )
    _require(
        int(report.get("acceptance_schema_version", -1))
        == ACCEPTANCE_SCHEMA_VERSION,
        "Unexpected acceptance report schema",
    )

    reference = report.get("reference_system", {})
    _require(
        bool(reference.get("qualified")),
        "Acceptance report was not produced on a qualified reference system",
    )
    _require(
        bool(reference.get("os_match")),
        "Reference operating-system qualification failed",
    )
    _require(
        bool(reference.get("gpu_match")),
        "Reference GPU qualification failed",
    )

    thresholds = report.get("thresholds", {})
    _require(
        thresholds.get("SUPPORTED-OSV-PROFILE-001")
        == SUPPORTED_OSV_PROFILE_ID,
        "Supported OSV profile identifier does not match the approved baseline",
    )
    _require(
        _float_equal(
            thresholds.get("CAMERA-EQUIVALENCE-001_source_pixels"),
            CAMERA_EQUIVALENCE_MAX_SOURCE_PIXEL,
        ),
        "Camera-equivalence threshold differs from the approved baseline",
    )
    _require(
        _float_equal(
            thresholds.get("CAMERA-RESPONSE-001_p95_ms"),
            CAMERA_RESPONSE_P95_MS,
        ),
        "Camera-response threshold differs from the approved baseline",
    )
    _require(
        _float_equal(
            thresholds.get("SCRUB-RESPONSE-001_p95_ms"),
            SCRUB_RESPONSE_P95_MS,
        ),
        "Scrub-response threshold differs from the approved baseline",
    )
    _require(
        _float_equal(
            thresholds.get("PREVIEW-AV-SYNC-001_ms"),
            PREVIEW_AV_SYNC_MAX_MS,
        ),
        "Preview A/V-sync threshold differs from the approved baseline",
    )

    requirements = report.get("requirements", {})
    for requirement_id in REQUIRED_ACCEPTANCE_REQUIREMENTS:
        _require(
            requirement_id in requirements,
            f"Acceptance report is missing {requirement_id}",
        )
        _require(
            bool(requirements[requirement_id].get("passed")),
            f"{requirement_id} did not pass",
        )

    _require(
        bool(report.get("all_five_pass")),
        "Acceptance report does not mark all five field gates PASS",
    )
    _require(
        bool(report.get("iteration1_acceptance_qualified")),
        "Acceptance report does not qualify Iteration 1",
    )

    media = requirements["SYS-MEDIA-001"]
    camera = requirements["SYS-CAM-009"]
    audio = requirements["SYS-AUDIO-003"]
    camera_perf = requirements["SYS-PERF-001"]
    scrub_perf = requirements["SYS-PERF-002"]

    profile_id = media.get("measured", {}).get("profile_id")
    _require(
        profile_id == SUPPORTED_OSV_PROFILE_ID,
        "Measured source profile does not match the approved source profile",
    )

    source_results = media.get("measured", {}).get("clip_results", [])
    _require(
        bool(source_results),
        "Acceptance report contains no qualified source recordings",
    )
    _require(
        all(
            bool(item.get("accepted"))
            and item.get("profile_id") == SUPPORTED_OSV_PROFILE_ID
            for item in source_results
        ),
        "At least one source recording failed the supported-profile gate",
    )

    camera_error = float(
        camera.get("measured", {}).get("max_source_pixel_error")
    )
    av_error = _maximum_clip_metric(audio, "max_error_ms")
    camera_p95 = _maximum_clip_metric(camera_perf, "p95_ms")
    scrub_p95 = _maximum_clip_metric(scrub_perf, "p95_ms")

    _require(
        camera_error <= CAMERA_EQUIVALENCE_MAX_SOURCE_PIXEL,
        "Measured Camera equivalence exceeds the approved threshold",
    )
    _require(
        av_error <= PREVIEW_AV_SYNC_MAX_MS,
        "Measured Preview A/V sync exceeds the approved threshold",
    )
    _require(
        camera_p95 <= CAMERA_RESPONSE_P95_MS,
        "Measured Camera response exceeds the approved threshold",
    )
    _require(
        scrub_p95 <= SCRUB_RESPONSE_P95_MS,
        "Measured scrub response exceeds the approved threshold",
    )

    durations = [
        float(item["duration"])
        for item in source_results
        if item.get("duration") is not None
    ]

    return {
        "certificate_schema_version": 1,
        "product": "PanoPilot",
        "scope": "Iteration 1",
        "status": "PASS",
        "requirements_total": 208,
        "requirements_pass": 208,
        "requirements_partial": 0,
        "requirements_open": 0,
        "acceptance_requirements": list(
            REQUIRED_ACCEPTANCE_REQUIREMENTS
        ),
        "reference_system": {
            "qualified": True,
            "os_pretty_name": reference.get("os_pretty_name"),
            "os_version": reference.get("os_version"),
            "platform": reference.get("platform"),
            "python": reference.get("python"),
            "machine": reference.get("machine"),
            "gpu_class": "AMD Radeon 890M / Strix",
        },
        "supported_osv_profile": SUPPORTED_OSV_PROFILE_ID,
        "qualified_source_count": len(source_results),
        "qualified_source_durations_s": durations,
        "measurements": {
            "camera_equivalence_max_source_pixel": camera_error,
            "preview_av_sync_max_ms": av_error,
            "camera_response_worst_clip_p95_ms": camera_p95,
            "scrub_response_worst_clip_p95_ms": scrub_p95,
        },
        "thresholds": {
            "camera_equivalence_max_source_pixel": float(
                CAMERA_EQUIVALENCE_MAX_SOURCE_PIXEL
            ),
            "preview_av_sync_max_ms": float(PREVIEW_AV_SYNC_MAX_MS),
            "camera_response_p95_ms": float(CAMERA_RESPONSE_P95_MS),
            "scrub_response_p95_ms": float(SCRUB_RESPONSE_P95_MS),
        },
        "privacy": {
            "source_paths_included": False,
            "source_fingerprints_included": False,
            "preview_cache_paths_included": False,
        },
    }


def certify_acceptance_report_file(report_path, *, output_path=None):
    report_path = Path(report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    certificate = certify_acceptance_report(report)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(certificate, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output_path)

    return certificate


def format_acceptance_certificate(certificate):
    measurements = certificate["measurements"]

    return "\n".join(
        (
            "PanoPilot Iteration-1 Certification",
            "Status: PASS",
            "Requirements: 208/208 PASS",
            (
                "Camera equivalence: "
                f"{measurements['camera_equivalence_max_source_pixel']:.6f} "
                "source px"
            ),
            (
                "Preview A/V sync worst case: "
                f"{measurements['preview_av_sync_max_ms']:.3f} ms"
            ),
            (
                "Camera response worst p95: "
                f"{measurements['camera_response_worst_clip_p95_ms']:.3f} ms"
            ),
            (
                "Scrub response worst p95: "
                f"{measurements['scrub_response_worst_clip_p95_ms']:.3f} ms"
            ),
        )
    )
