import numpy as np

from panopilot.spherical_stabilization import (
    _fill_vector_series,
)


def test_spherical_series_fill_interpolates_invalid_motion_without_jumps():
    values = np.array(
        [
            [0.0, 0.0],
            [2.0, -1.0],
            [99.0, 99.0],
            [6.0, -3.0],
        ],
        dtype=np.float64,
    )
    valid = np.array(
        [
            True,
            True,
            False,
            True,
        ]
    )

    out = _fill_vector_series(
        values,
        valid,
    )

    assert np.allclose(
        out[2],
        [
            4.0,
            -2.0,
        ],
    )
