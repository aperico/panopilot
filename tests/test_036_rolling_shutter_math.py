import math

import numpy as np

from panopilot.rolling_shutter import (
    apply_rotation_vector_field,
    build_frame_correction,
    candidate_signed_readouts,
    choose_calibration,
    corrected_panorama_map_for_lens,
    directions_to_panorama_map,
    panorama_map_to_directions,
)
from panopilot.stabilization import (
    StabilizationTrajectory,
)


def _quat_z(degrees):
    half = math.radians(
        degrees
    ) / 2.0
    return np.array(
        [
            math.cos(half),
            0.0,
            0.0,
            math.sin(half),
        ],
        dtype=np.float64,
    )


def _constant_velocity_trajectory():
    times = np.array(
        [
            -0.010,
            0.000,
            0.010,
        ],
        dtype=np.float64,
    )
    raw = np.asarray(
        [
            _quat_z(-2.0),
            _quat_z(0.0),
            _quat_z(2.0),
        ],
        dtype=np.float64,
    )
    return StabilizationTrajectory(
        times=times,
        raw_quaternions=raw,
        stable_quaternions=raw.copy(),
        diagnostics={},
    )


def test_panorama_direction_roundtrip():
    map_x = np.array(
        [
            [0.5, 50.25, 199.5],
            [320.0, 639.0, 100.0],
        ],
        dtype=np.float32,
    )
    map_y = np.array(
        [
            [10.0, 40.5, 90.25],
            [100.0, 150.0, 200.0],
        ],
        dtype=np.float32,
    )

    directions = panorama_map_to_directions(
        map_x,
        map_y,
        640,
        320,
    )
    out_x, out_y = directions_to_panorama_map(
        directions,
        640,
        320,
    )

    # X is periodic. These points are away from the seam, so direct equality
    # is expected.
    assert np.allclose(
        out_x,
        map_x,
        atol=2e-4,
    )
    assert np.allclose(
        out_y,
        map_y,
        atol=2e-4,
    )


def test_constant_velocity_readout_has_opposite_top_bottom_rotations():
    correction = build_frame_correction(
        _constant_velocity_trajectory(),
        0.0,
        8.0,
        reference_offset_ms=0.0,
    )

    top = correction.top_rotation_vector
    bottom = correction.bottom_rotation_vector

    assert np.linalg.norm(top) > 1e-5
    assert np.linalg.norm(bottom) > 1e-5
    assert float(
        np.dot(
            top,
            bottom,
        )
    ) < 0.0
    assert np.allclose(
        top,
        -bottom,
        atol=2e-4,
    )


def test_center_sensor_row_is_nearly_unchanged_for_symmetric_readout():
    correction = build_frame_correction(
        _constant_velocity_trajectory(),
        0.0,
        8.0,
        reference_offset_ms=0.0,
    )

    map_x = np.full(
        (
            4,
            5,
        ),
        320.0,
        dtype=np.float32,
    )
    map_y = np.full(
        (
            4,
            5,
        ),
        160.0,
        dtype=np.float32,
    )
    lens_y = np.full(
        (
            4,
            5,
        ),
        499.5,
        dtype=np.float32,
    )

    corrected_x, corrected_y = (
        corrected_panorama_map_for_lens(
            map_x,
            map_y,
            lens_y,
            source_height=1000,
            panorama_width=640,
            panorama_height=320,
            correction=correction,
        )
    )

    assert np.allclose(
        corrected_x,
        map_x,
        atol=1e-3,
    )
    assert np.allclose(
        corrected_y,
        map_y,
        atol=1e-3,
    )


def test_reference_offset_changes_mid_row_correction():
    symmetric = build_frame_correction(
        _constant_velocity_trajectory(),
        0.0,
        8.0,
        reference_offset_ms=0.0,
    )
    shifted = build_frame_correction(
        _constant_velocity_trajectory(),
        0.0,
        8.0,
        reference_offset_ms=2.0,
    )

    symmetric_center = 0.5 * (
        symmetric.top_rotation_vector
        + symmetric.bottom_rotation_vector
    )
    shifted_center = 0.5 * (
        shifted.top_rotation_vector
        + shifted.bottom_rotation_vector
    )

    assert np.linalg.norm(
        symmetric_center
    ) < 1e-4
    assert np.linalg.norm(
        shifted_center
    ) > 1e-4


def test_candidate_readouts_are_bounded_and_search_both_directions():
    candidates = candidate_signed_readouts(
        10.0
    )

    assert 0.0 in candidates
    assert min(candidates) < 0.0
    assert max(candidates) > 0.0
    assert max(
        abs(value)
        for value in candidates
    ) < 10.0


def test_joint_calibration_selects_materially_better_readout_and_offset():
    calibration = choose_calibration(
        {
            (0.0, 0.0): 2.0,
            (7.5, 0.0): 1.8,
            (7.5, -2.0): 1.2,
            (-7.5, 2.0): 2.4,
        },
        source_frame_period_ms=10.0,
        sample_pair_count=3,
        minimum_improvement_fraction=0.05,
    )

    assert calibration.signed_readout_ms == 7.5
    assert calibration.reference_offset_ms == -2.0
    assert calibration.direction == "top-to-bottom"
    assert calibration.improvement_fraction > 0.3


def test_joint_calibration_falls_back_to_zero_when_gain_is_too_small():
    calibration = choose_calibration(
        {
            (0.0, 0.0): 2.0,
            (8.0, -1.0): 1.94,
        },
        source_frame_period_ms=10.0,
        sample_pair_count=2,
        minimum_improvement_fraction=0.05,
    )

    assert calibration.signed_readout_ms == 0.0
    assert calibration.reference_offset_ms == 0.0
    assert calibration.direction == "none"


def test_piecewise_row_table_uses_eleven_highrate_subdivisions():
    correction = build_frame_correction(
        _constant_velocity_trajectory(),
        0.0,
        8.0,
        subdivisions=11,
    )

    assert correction.row_fractions.shape == (
        11,
    )
    assert correction.row_rotation_vectors.shape == (
        11,
        3,
    )
    assert correction.row_fractions[0] == 0.0
    assert correction.row_fractions[-1] == 1.0


def test_negative_readout_reverses_top_bottom_row_motion():
    positive = build_frame_correction(
        _constant_velocity_trajectory(),
        0.0,
        8.0,
    )
    negative = build_frame_correction(
        _constant_velocity_trajectory(),
        0.0,
        -8.0,
    )

    assert np.allclose(
        positive.top_rotation_vector,
        negative.bottom_rotation_vector,
        atol=2e-4,
    )
    assert np.allclose(
        positive.bottom_rotation_vector,
        negative.top_rotation_vector,
        atol=2e-4,
    )
