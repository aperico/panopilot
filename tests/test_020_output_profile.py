import pytest

from panopilot.output_profile import (
    output_profile_for_aspect,
)


def test_iteration1_16_9_output_profile():
    profile = output_profile_for_aspect(
        "16:9",
        fps="30",
    )

    assert profile.width == 1920
    assert profile.height == 1080
    assert profile.fps == pytest.approx(
        30.0
    )


def test_iteration1_9_16_output_profile():
    profile = output_profile_for_aspect(
        "9:16",
        fps="30",
    )

    assert profile.width == 1080
    assert profile.height == 1920
    assert profile.fps == pytest.approx(
        30.0
    )
