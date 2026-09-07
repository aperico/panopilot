import copy

import pytest

from panopilot.acceptance_certificate import (
    AcceptanceCertificateError,
    certify_acceptance_report,
)
from panopilot.source_validation import (
    SUPPORTED_OSV_PROFILE_ID,
)


def _report():
    return {
        "acceptance_schema_version": 1,
        "reference_system": {
            "qualified": True,
            "os_match": True,
            "gpu_match": True,
            "os_pretty_name": "Fedora Linux 44",
            "os_version": "44",
            "platform": "Linux-test",
            "python": "3.14",
            "machine": "x86_64",
        },
        "thresholds": {
            "SUPPORTED-OSV-PROFILE-001": (
                SUPPORTED_OSV_PROFILE_ID
            ),
            "CAMERA-EQUIVALENCE-001_source_pixels": 0.05,
            "CAMERA-RESPONSE-001_p95_ms": 100.0,
            "SCRUB-RESPONSE-001_p95_ms": 250.0,
            "PREVIEW-AV-SYNC-001_ms": 100.0,
        },
        "requirements": {
            "SYS-MEDIA-001": {
                "passed": True,
                "measured": {
                    "profile_id": (
                        SUPPORTED_OSV_PROFILE_ID
                    ),
                    "clip_results": [
                        {
                            "source": "/private/source.OSV",
                            "accepted": True,
                            "profile_id": (
                                SUPPORTED_OSV_PROFILE_ID
                            ),
                            "duration": 6.016,
                            "identity": {
                                "fingerprint": "secret",
                            },
                        }
                    ],
                },
            },
            "SYS-CAM-009": {
                "passed": True,
                "measured": {
                    "max_source_pixel_error": 0.0435,
                },
            },
            "SYS-AUDIO-003": {
                "passed": True,
                "measured": {
                    "clip_results": [
                        {
                            "max_error_ms": 35.0,
                            "preview": "/private/cache.mp4",
                        }
                    ],
                },
            },
            "SYS-PERF-001": {
                "passed": True,
                "measured": {
                    "clip_results": [
                        {
                            "p95_ms": 12.8,
                        }
                    ],
                },
            },
            "SYS-PERF-002": {
                "passed": True,
                "measured": {
                    "clip_results": [
                        {
                            "p95_ms": 101.4,
                        }
                    ],
                },
            },
        },
        "all_five_pass": True,
        "iteration1_acceptance_qualified": True,
    }


def test_certifier_closes_iteration1_and_sanitizes_private_source_evidence():
    certificate = certify_acceptance_report(
        _report()
    )

    assert certificate[
        "status"
    ] == "PASS"
    assert certificate[
        "requirements_pass"
    ] == 208
    assert certificate[
        "requirements_partial"
    ] == 0
    assert certificate[
        "requirements_open"
    ] == 0

    serialized = str(
        certificate
    )

    assert "/private/" not in serialized
    assert "secret" not in serialized
    assert certificate[
        "privacy"
    ][
        "source_paths_included"
    ] is False


def test_certifier_rejects_a_tampered_acceptance_threshold():
    report = _report()
    report[
        "thresholds"
    ][
        "SCRUB-RESPONSE-001_p95_ms"
    ] = 999.0

    with pytest.raises(
        AcceptanceCertificateError,
        match="Scrub-response threshold",
    ):
        certify_acceptance_report(
            report
        )


def test_certifier_rejects_failed_field_gate():
    report = _report()
    report[
        "requirements"
    ][
        "SYS-AUDIO-003"
    ][
        "passed"
    ] = False

    with pytest.raises(
        AcceptanceCertificateError,
        match="SYS-AUDIO-003",
    ):
        certify_acceptance_report(
            report
        )
