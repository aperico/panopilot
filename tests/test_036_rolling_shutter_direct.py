import numpy as np

from panopilot.direct_render import (
    DirectLensRenderer,
)
from panopilot.rolling_shutter import (
    RollingShutterFrameCorrection,
)


class FakeMapper:
    pass


def _mapper():
    width = 240
    height = 120
    mapper = FakeMapper()

    xx = np.broadcast_to(
        np.arange(
            width,
            dtype=np.float32,
        )[None, :],
        (
            height,
            width,
        ),
    ).copy()
    yy = np.broadcast_to(
        np.arange(
            height,
            dtype=np.float32,
        )[:, None],
        (
            height,
            width,
        ),
    ).copy()

    mapper.map0_x = xx
    mapper.map0_y = yy
    mapper.map1_x = xx
    mapper.map1_y = yy
    mapper.w0 = np.full(
        (
            height,
            width,
        ),
        0.5,
        dtype=np.float32,
    )
    mapper.w1 = np.full_like(
        mapper.w0,
        0.5,
    )
    mapper.out_w = width
    mapper.out_h = height
    return mapper


def test_zero_readout_is_exact_direct_map_baseline():
    renderer = DirectLensRenderer(
        _mapper()
    )

    map_x = np.broadcast_to(
        np.linspace(
            10.0,
            220.0,
            64,
            dtype=np.float32,
        )[None, :],
        (
            32,
            64,
        ),
    ).copy()
    map_y = np.broadcast_to(
        np.linspace(
            10.0,
            100.0,
            32,
            dtype=np.float32,
        )[:, None],
        (
            32,
            64,
        ),
    ).copy()

    baseline = renderer.compose_maps(
        map_x,
        map_y,
    )
    zero = renderer.compose_maps(
        map_x,
        map_y,
        rolling_shutter=(
            RollingShutterFrameCorrection(
                signed_readout_ms=0.0,
                reference_source_time=0.0,
                reference_offset_ms=0.0,
                top_rotation_vector=np.zeros(
                    3,
                    dtype=np.float64,
                ),
                bottom_rotation_vector=np.zeros(
                    3,
                    dtype=np.float64,
                ),
            )
        ),
    )

    assert np.array_equal(
        baseline.lens0_x,
        zero.lens0_x,
    )
    assert np.array_equal(
        baseline.lens0_y,
        zero.lens0_y,
    )
    assert np.array_equal(
        baseline.lens1_x,
        zero.lens1_x,
    )
    assert np.array_equal(
        baseline.weight0,
        zero.weight0,
    )


def test_nonzero_readout_changes_source_sampling_geometry():
    renderer = DirectLensRenderer(
        _mapper()
    )

    map_x = np.broadcast_to(
        np.linspace(
            20.0,
            210.0,
            64,
            dtype=np.float32,
        )[None, :],
        (
            32,
            64,
        ),
    ).copy()
    map_y = np.broadcast_to(
        np.linspace(
            10.0,
            105.0,
            32,
            dtype=np.float32,
        )[:, None],
        (
            32,
            64,
        ),
    ).copy()

    baseline = renderer.compose_maps(
        map_x,
        map_y,
    )
    correction = RollingShutterFrameCorrection(
        signed_readout_ms=8.0,
        reference_source_time=0.0,
        reference_offset_ms=0.0,
        top_rotation_vector=np.array(
            [
                0.0,
                -0.02,
                0.0,
            ],
            dtype=np.float64,
        ),
        bottom_rotation_vector=np.array(
            [
                0.0,
                0.02,
                0.0,
            ],
            dtype=np.float64,
        ),
        iterations=2,
    )
    corrected = renderer.compose_maps(
        map_x,
        map_y,
        rolling_shutter=correction,
    )

    assert not np.allclose(
        corrected.lens0_x,
        baseline.lens0_x,
    )
