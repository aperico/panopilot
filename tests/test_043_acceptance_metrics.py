from pathlib import Path

import panopilot.acceptance as acceptance
from panopilot.acceptance import (
    CAMERA_EQUIVALENCE_MAX_SOURCE_PIXEL,
    PREVIEW_AV_SYNC_MAX_MS,
    camera_equivalence_metrics,
    preview_av_sync_metrics,
)


def test_camera_equivalence_meets_resolved_geometry_threshold():
    metrics = camera_equivalence_metrics()

    assert metrics[
        "passed"
    ] is True
    assert (
        metrics[
            "max_source_pixel_error"
        ]
        <= CAMERA_EQUIVALENCE_MAX_SOURCE_PIXEL
    )
    assert len(
        metrics[
            "observations"
        ]
    ) == 12


def test_preview_av_sync_uses_start_and_end_alignment(
    monkeypatch,
):
    monkeypatch.setattr(
        acceptance,
        "probe_source",
        lambda _path: {
            "streams": [
                {
                    "codec_type": "video",
                    "start_time": "0.000",
                    "duration": "5.000",
                    "disposition": {
                        "attached_pic": 0,
                    },
                },
                {
                    "codec_type": "audio",
                    "start_time": "0.020",
                    "duration": "4.950",
                },
            ]
        },
    )

    metrics = preview_av_sync_metrics(
        "preview.mp4"
    )

    assert metrics[
        "applicable"
    ] is True
    assert abs(
        metrics[
            "max_error_ms"
        ]
        - 30.0
    ) < 1e-9
    assert metrics[
        "passed"
    ] is True


def test_preview_av_sync_rejects_more_than_resolved_tolerance(
    monkeypatch,
):
    monkeypatch.setattr(
        acceptance,
        "probe_source",
        lambda _path: {
            "streams": [
                {
                    "codec_type": "video",
                    "start_time": "0.000",
                    "duration": "5.000",
                    "disposition": {
                        "attached_pic": 0,
                    },
                },
                {
                    "codec_type": "audio",
                    "start_time": "0.150",
                    "duration": "4.850",
                },
            ]
        },
    )

    metrics = preview_av_sync_metrics(
        "preview.mp4"
    )

    assert metrics[
        "max_error_ms"
    ] > PREVIEW_AV_SYNC_MAX_MS
    assert metrics[
        "passed"
    ] is False


def test_preview_without_audio_is_not_an_av_sync_failure(
    monkeypatch,
):
    monkeypatch.setattr(
        acceptance,
        "probe_source",
        lambda _path: {
            "streams": [
                {
                    "codec_type": "video",
                    "start_time": "0.000",
                    "duration": "5.000",
                    "disposition": {
                        "attached_pic": 0,
                    },
                },
            ]
        },
    )

    metrics = preview_av_sync_metrics(
        "preview.mp4"
    )

    assert metrics[
        "applicable"
    ] is False
    assert metrics[
        "passed"
    ] is True
