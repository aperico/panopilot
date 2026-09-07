import pytest

from panopilot.source_validation import (
    SUPPORTED_OSV_PROFILE_ID,
    supported_osv_profile_observation,
    validate_supported_osv_profile,
)


def _probe(
    *,
    codec="hevc",
    width=1920,
    height=1920,
    fps="100/1",
    second_start="0.000000",
):
    return {
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": codec,
                "width": width,
                "height": height,
                "avg_frame_rate": fps,
                "r_frame_rate": fps,
                "start_time": "0.000000",
                "disposition": {
                    "attached_pic": 0,
                },
            },
            {
                "index": 1,
                "codec_type": "video",
                "codec_name": codec,
                "width": width,
                "height": height,
                "avg_frame_rate": fps,
                "r_frame_rate": fps,
                "start_time": second_start,
                "disposition": {
                    "attached_pic": 0,
                },
            },
        ],
        "format": {
            "duration": "6.016",
        },
    }


def test_validated_iteration1_osv_profile_is_explicit():
    probe = _probe()

    observed = validate_supported_osv_profile(
        probe
    )

    assert (
        observed[
            "profile_id"
        ]
        == SUPPORTED_OSV_PROFILE_ID
    )
    assert (
        observed[
            "lens_count"
        ]
        == 2
    )
    assert all(
        item[
            "codec"
        ]
        == "hevc"
        for item in observed[
            "lenses"
        ]
    )
    assert all(
        item[
            "fps"
        ]
        == 100.0
        for item in observed[
            "lenses"
        ]
    )


@pytest.mark.parametrize(
    "kwargs,match",
    [
        (
            {
                "codec": "h264",
            },
            "HEVC",
        ),
        (
            {
                "width": 3840,
                "height": 3840,
            },
            "1920x1920",
        ),
        (
            {
                "fps": "50/1",
            },
            "100 fps",
        ),
        (
            {
                "second_start": "0.050000",
            },
            "synchronized",
        ),
    ],
)
def test_unqualified_source_modes_are_not_silently_claimed_supported(
    kwargs,
    match,
):
    with pytest.raises(
        RuntimeError,
        match=match,
    ):
        validate_supported_osv_profile(
            _probe(
                **kwargs
            )
        )


def test_profile_observation_is_non_mutating():
    probe = _probe()
    observed = (
        supported_osv_profile_observation(
            probe
        )
    )

    assert observed[
        "lenses"
    ][
        0
    ][
        "width"
    ] == 1920
