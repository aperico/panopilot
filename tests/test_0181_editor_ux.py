from panopilot.explore import (
    compact_camera_text,
    compact_trim_labels,
)


def test_compact_trim_labels_do_not_duplicate_full_sentence():
    values = compact_trim_labels(
        1.05,
        5.05,
    )

    assert values == {
        "in": "IN  00:01.050",
        "out": "OUT  00:05.050",
        "duration": "CLIP  00:04.000",
    }

    for value in values.values():
        assert len(value) < 20


def test_compact_camera_text():
    text = compact_camera_text(
        10.0,
        -3.0,
        75.0,
        "16:9",
    )

    assert text == (
        "Yaw +10.0°   "
        "Pitch -3.0°   "
        "FOV 75.0°   "
        "16:9"
    )


def test_loading_module_imports_without_constructing_ui():
    from panopilot.loading import (
        run_with_loading_screen,
    )

    assert callable(
        run_with_loading_screen
    )
