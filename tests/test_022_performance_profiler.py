import time

import pytest

from panopilot.performance import (
    StageProfiler,
    dominant_stage,
    format_performance_summary,
)


def test_stage_profiler_aggregates_calls_and_seconds():
    profiler = StageProfiler()
    profiler.add(
        "a",
        2.0,
        calls=2,
    )
    profiler.add(
        "b",
        1.0,
        calls=1,
    )

    summary = profiler.summary(
        total_seconds=4.0
    )

    assert summary["a"]["seconds"] == pytest.approx(
        2.0
    )
    assert summary["a"]["calls"] == 2
    assert summary["a"]["mean_ms"] == pytest.approx(
        1000.0
    )
    assert summary["a"]["share_percent"] == pytest.approx(
        50.0
    )


def test_dominant_stage():
    summary = {
        "stitch": {
            "seconds": 8.0,
            "share_percent": 60.0,
        },
        "projection": {
            "seconds": 3.0,
            "share_percent": 22.5,
        },
    }

    result = dominant_stage(
        summary
    )

    assert result["name"] == "stitch"
    assert result["seconds"] == pytest.approx(
        8.0
    )


def test_format_performance_summary_is_user_readable():
    text = format_performance_summary(
        {
            "processing_seconds": 20.0,
            "frames": 100,
            "processing_fps": 5.0,
            "dominant_video_stage": {
                "name": "factory_stitch",
                "share_percent": 55.0,
            },
            "video_stage_timings": {
                "factory_stitch": {
                    "seconds": 11.0,
                    "share_percent": 55.0,
                }
            },
        }
    )

    assert "Total export: 20.00s" in text
    assert "factory_stitch" in text
    assert "55.0%" in text
