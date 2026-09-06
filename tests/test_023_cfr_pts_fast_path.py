import subprocess

import pytest

from panopilot.source import (
    source_frame_times,
)


def _cfr_probe(
    fps="100/1",
    *,
    nominal=None,
    start_time="0.000000",
):
    return {
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "avg_frame_rate": fps,
                "r_frame_rate": (
                    nominal
                    if nominal is not None
                    else fps
                ),
                "start_time": start_time,
            }
        ]
    }


def test_source_frame_times_uses_cfr_probe_without_second_ffprobe(
    monkeypatch,
):
    def fail_run(*args, **kwargs):
        raise AssertionError(
            "per-frame ffprobe should not run for safely detected CFR source"
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        fail_run,
    )

    times, diagnostics = source_frame_times(
        "source.OSV",
        0,
        0.0,
        0.10,
        probe=_cfr_probe(),
        return_diagnostics=True,
    )

    assert diagnostics == {
        "method": "cfr-stream-metadata",
        "frame_rate": 100.0,
        "ffprobe_frame_scan": False,
    }
    assert times[:4] == pytest.approx(
        [
            0.0,
            0.01,
            0.02,
            0.03,
        ]
    )


def test_cfr_metadata_reproduces_100fps_to_30fps_nearest_pts_pattern():
    from panopilot.source import (
        preview_exposure_times,
    )

    source_times, diagnostics = (
        source_frame_times(
            "source.OSV",
            0,
            0.0,
            0.20,
            probe=_cfr_probe(),
            return_diagnostics=True,
        )
    )

    mapped, mapping = (
        preview_exposure_times(
            source_times,
            start=0.0,
            duration=0.20,
            output_fps=30.0,
        )
    )

    assert diagnostics[
        "frame_rate"
    ] == 100.0
    assert mapped[:4] == pytest.approx(
        [
            0.0,
            0.03,
            0.07,
            0.10,
        ]
    )
    assert mapping[
        "mean_abs_mapping_error_ms"
    ] == pytest.approx(
        2.2222222222,
        abs=1e-6,
    )
    assert mapping[
        "max_abs_mapping_error_ms"
    ] == pytest.approx(
        3.3333333333,
        abs=1e-6,
    )


def test_mismatched_nominal_and_average_rate_falls_back_to_ffprobe(
    monkeypatch,
):
    payload = (
        '{"frames":['
        '{"best_effort_timestamp_time":"0.000000"},'
        '{"best_effort_timestamp_time":"0.010000"}'
        ']}'
    )

    class Result:
        stdout = payload

    calls = []

    def fake_run(*args, **kwargs):
        calls.append(
            args
        )
        return Result()

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run,
    )

    times, diagnostics = source_frame_times(
        "source.mp4",
        0,
        0.0,
        0.10,
        probe=_cfr_probe(
            "100/1",
            nominal="30000/1001",
        ),
        return_diagnostics=True,
    )

    assert calls
    assert diagnostics[
        "method"
    ] == "ffprobe-frame-scan"
    assert times == pytest.approx(
        [
            0.0,
            0.01,
        ]
    )
