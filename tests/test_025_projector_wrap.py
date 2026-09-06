import numpy as np
import pytest

from panopilot.virtual_camera import (
    _wrap_equirectangular_x_inplace,
)


@pytest.mark.parametrize(
    "width",
    [
        720,
        1920,
        3840,
    ],
)
def test_bounded_wrap_matches_numpy_mod_exactly(
    width,
):
    # This spans the exact range produced by atan2 longitude conversion,
    # including seam-adjacent fractional coordinates.
    values = np.array(
        [
            -0.5,
            -0.25,
            0.0,
            0.25,
            width / 2.0,
            width - 1.0,
            width - 0.5,
            float(width),
        ],
        dtype=np.float32,
    )

    expected = np.mod(
        values,
        np.float32(
            width
        ),
    )

    actual = values.copy()
    returned = (
        _wrap_equirectangular_x_inplace(
            actual,
            width,
        )
    )

    assert returned is actual
    assert np.array_equal(
        actual,
        expected,
    )


def test_bounded_wrap_matches_mod_for_dense_projector_range():
    width = 3840
    values = np.linspace(
        -0.5,
        width - 0.5,
        100_001,
        dtype=np.float32,
    )

    expected = np.mod(
        values,
        np.float32(
            width
        ),
    )
    actual = values.copy()

    _wrap_equirectangular_x_inplace(
        actual,
        width,
    )

    assert np.array_equal(
        actual,
        expected,
    )
