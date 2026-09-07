from panopilot.spherical_stabilization import (
    _roll_coherence_weight,
)


def test_visual_roll_is_fully_trusted_when_spatial_bands_agree():
    assert (
        _roll_coherence_weight(
            0.0,
            0.0,
        )
        > 0.99
    )


def test_visual_roll_is_attenuated_when_bands_disagree():
    moderate = _roll_coherence_weight(
        0.8,
        0.2,
    )
    severe = _roll_coherence_weight(
        1.5,
        1.0,
    )

    assert moderate < 0.5
    assert severe < moderate
    assert severe < 0.05
