from types import SimpleNamespace

from panopilot.export_ui import (
    ExportProgressModel,
    build_export_summary,
    format_bytes,
    format_duration,
)


def test_export_progress_maps_render_frames_and_eta():
    model = ExportProgressModel(
        expected_render_passes=1,
        started_at=0.0,
    )

    snapshot = model.update(
        {
            "stage": "render-frame",
            "message": "Rendering",
            "percent": 50.0,
            "render_pass_index": 1,
        },
        now=20.0,
    )

    assert 50.0 < snapshot.percent < 55.0
    assert snapshot.elapsed_seconds == 20.0
    assert snapshot.remaining_seconds is not None
    assert snapshot.remaining_seconds > 0.0


def test_export_progress_never_runs_backwards():
    model = ExportProgressModel(
        expected_render_passes=1,
        started_at=0.0,
    )

    first = model.update(
        {
            "stage": "render-frame",
            "percent": 80.0,
            "message": "Rendering",
        },
        now=10.0,
    )
    second = model.update(
        {
            "stage": "inspect",
            "message": "Inspecting",
        },
        now=11.0,
    )

    assert second.percent == first.percent


def test_calibration_progress_accounts_for_clip_and_candidate():
    model = ExportProgressModel(
        expected_render_passes=1,
        started_at=0.0,
    )

    first_clip = model.update(
        {
            "stage": "rolling-shutter-calibration-progress",
            "message": "Calibrating",
            "clip_index": 1,
            "clip_count": 2,
            "candidate_index": 20,
            "candidate_total": 40,
        },
        now=5.0,
    )
    second_clip = model.update(
        {
            "stage": "rolling-shutter-calibration-progress",
            "message": "Calibrating",
            "clip_index": 2,
            "clip_count": 2,
            "candidate_index": 20,
            "candidate_total": 40,
        },
        now=10.0,
    )

    assert 5.0 < first_clip.percent < 10.0
    assert second_clip.percent > first_clip.percent
    assert second_clip.percent < 15.0


def test_two_render_passes_have_distinct_progress_ranges():
    model = ExportProgressModel(
        expected_render_passes=2,
        started_at=0.0,
    )

    first_end = model.update(
        {
            "stage": "render-frame",
            "message": "Initial render",
            "percent": 100.0,
            "render_pass_index": 1,
        },
        now=30.0,
    )
    second_mid = model.update(
        {
            "stage": "render-frame",
            "message": "Final re-render",
            "percent": 50.0,
            "render_pass_index": 2,
        },
        now=50.0,
    )

    assert 50.0 < first_end.percent < 55.0
    assert second_mid.percent > first_end.percent
    assert second_mid.percent < 90.0


def test_export_summary_uses_saved_size_and_quality(tmp_path):
    project = SimpleNamespace(
        output_aspect="16:9",
        output_resolution="720p",
        output_quality="very-high",
        stabilization_amount=0.75,
        clips=[object(), object()],
    )

    summary = build_export_summary(
        project,
        tmp_path / "family.mp4",
        timeline_duration=61.2,
    )

    assert "1280×720" in summary["text"]
    assert "Very High" in summary["text"]
    assert "Stabilization: 75%" in summary["text"]
    assert "1:01" in summary["text"]


def test_human_format_helpers():
    assert format_duration(65.0) == "1:05"
    assert format_duration(3661.0) == "1:01:01"
    assert format_bytes(1024 * 1024) == "1.0 MB"
