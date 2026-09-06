import pytest

from panopilot.output_profile import (
    output_profile_for_aspect,
)
from panopilot.project_export import (
    EXPORT_AV_SYNC_TOLERANCE_S,
)


def test_export_av_sync_policy_is_50ms():
    assert EXPORT_AV_SYNC_TOLERANCE_S == pytest.approx(
        0.050
    )


def test_output_profiles_are_h264_delivery_friendly_even_dimensions():
    for aspect in (
        "16:9",
        "9:16",
    ):
        profile = output_profile_for_aspect(
            aspect
        )
        assert profile.width % 2 == 0
        assert profile.height % 2 == 0
