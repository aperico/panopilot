"""Measure the final world-to-output rotation, including horizon leveling."""
import numpy as np
import pytest

from panopilot.attitude import (
    IMU_TO_FACTORY_EQUIRECT as BASIS,
    gravity_equirectangular, quat_to_matrix, smooth_unit_vectors_centered,
    stabilized_horizon_rotation,
)
from panopilot.stabilization import build_adaptive_trajectory


@pytest.mark.parametrize("axis", [0, 1, 2])
@pytest.mark.parametrize("amount", [.75, 1.0])
def test_combined_horizon_and_stabilization_rejects_shake(axis, amount):
    times = np.arange(0, 4, 1 / 100)
    angles = np.radians(6 * np.sin(2 * np.pi * 7 * times))
    quats = np.zeros((len(times), 4))
    quats[:, 0] = np.cos(angles / 2)
    quats[:, axis + 1] = np.sin(angles / 2)
    trajectory = build_adaptive_trajectory([
        {"source_time": t, "quat": q} for t, q in zip(times, quats)
    ], amount)
    gravity = smooth_unit_vectors_centered(
        [gravity_equirectangular(q) for q in quats], 10
    )
    raw_images, corrected_images = [], []
    for raw, smooth, g in zip(quats, trajectory.stable_quaternions, gravity):
        world_to_sensor = BASIS @ quat_to_matrix(raw).T @ BASIS.T
        correction, _ = stabilized_horizon_rotation(
            raw_quaternion=raw, smoothed_quaternion=smooth, leveled_gravity=g,
            stabilization_amount=amount, level_horizon=True,
        )
        raw_images.append(world_to_sensor)
        corrected_images.append(correction @ world_to_sensor)
    # Matrix second differences measure angular shake on all three axes.
    # Ignore edge settling to isolate repeated handheld oscillations.
    raw_rms = np.sqrt(np.mean(np.diff(raw_images[50:-50], n=2, axis=0) ** 2))
    final_rms = np.sqrt(np.mean(np.diff(corrected_images[50:-50], n=2, axis=0) ** 2))
    assert final_rms < raw_rms * .04, (axis, amount, final_rms / raw_rms)
