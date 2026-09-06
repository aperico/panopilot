import cv2
import numpy as np


def test_opencv_spatial_blend_matches_previous_numpy_reference():
    rng = np.random.default_rng(
        23
    )

    p0 = rng.integers(
        0,
        256,
        size=(
            120,
            240,
            3,
        ),
        dtype=np.uint8,
    )
    p1 = rng.integers(
        0,
        256,
        size=(
            120,
            240,
            3,
        ),
        dtype=np.uint8,
    )

    weight1 = np.linspace(
        0.0,
        1.0,
        240,
        dtype=np.float32,
    )[None, :]
    weight1 = np.broadcast_to(
        weight1,
        (
            120,
            240,
        ),
    ).copy()
    weight0 = (
        1.0
        - weight1
    )

    previous = (
        p0.astype(
            np.float32
        )
        * weight0[..., None]
        + p1.astype(
            np.float32
        )
        * weight1[..., None]
    )
    previous = np.clip(
        previous,
        0,
        255,
    ).astype(
        np.uint8
    )

    optimized = cv2.blendLinear(
        p0,
        p1,
        weight0,
        weight1,
    )

    difference = np.abs(
        previous.astype(
            np.int16
        )
        - optimized.astype(
            np.int16
        )
    )

    # blendLinear rounds at the final integer conversion whereas the original
    # NumPy path truncated. The spatial weighting itself is equivalent.
    assert int(
        difference.max()
    ) <= 1
    assert float(
        difference.mean()
    ) <= 0.51
