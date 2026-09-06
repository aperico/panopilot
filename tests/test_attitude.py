import numpy as np

from panopilot.attitude import (
    EQUIRECT_DOWN,
    IMU_TO_FACTORY_EQUIRECT,
    horizon_correction,
)


def test_imu_factory_axis_mapping():
    # IMU +Z = down maps to equirect -Y = down.
    mapped = IMU_TO_FACTORY_EQUIRECT @ np.array([0.0, 0.0, 1.0])
    assert np.allclose(mapped, EQUIRECT_DOWN)


def test_level_quaternion_needs_no_correction():
    # Identity BODY->WORLD means WORLD_DOWN is IMU +Z.
    correction, diagnostics = horizon_correction([1.0, 0.0, 0.0, 0.0])
    assert diagnostics["tilt_before_deg"] < 1e-9
    assert np.allclose(correction, np.eye(3), atol=1e-9)


def test_known_sample_quaternion_has_small_not_90_degree_tilt():
    # Frame ~2.0 s from the current golden Osmo 360 sample.
    q = [
        0.6060518622398376,
        0.0018640982452780008,
        -0.020065711811184883,
        -0.7951697707176208,
    ]
    _correction, diagnostics = horizon_correction(q)
    assert 1.0 < diagnostics["tilt_before_deg"] < 5.0
