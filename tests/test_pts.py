from panopilot.source import preview_exposure_times


def test_preview_exposure_times_select_nearest_source_pts():
    source = [0.00, 0.01, 0.02, 0.03, 0.04]

    mapped, diagnostics = preview_exposure_times(
        source,
        start=0.0,
        duration=0.04,
        output_fps=50.0,
    )

    assert mapped[:2] == [0.0, 0.02]
    assert diagnostics["used_actual_pts"] is True
