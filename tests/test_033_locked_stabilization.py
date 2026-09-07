import numpy as np

from panopilot.locked_stabilization import (
    _robust_polynomial_target,
    _segment_feasible_gain,
    _translation_matrices,
)


def test_locked_target_removes_high_frequency_wobble():
    x = np.linspace(-1.0, 1.0, 180)
    smooth_path = 30.0 * x + 5.0 * x * x
    wobble = 4.0 * np.sin(np.arange(180) * 0.73 * np.pi)
    path = smooth_path + wobble

    target = _robust_polynomial_target(path, degree=2)

    assert np.std(target - smooth_path) < 0.2
    assert np.std(path - target) > 2.0


def test_locked_crop_gain_is_one_constant_for_complete_segment():
    accumulated_x = np.zeros(20)
    accumulated_y = np.zeros(20)
    new_x = np.linspace(-200.0, 200.0, 20)
    new_y = np.linspace(-100.0, 100.0, 20)

    gain = _segment_feasible_gain(
        accumulated_x,
        accumulated_y,
        new_x,
        new_y,
        0,
        20,
        margin_x=100.0,
        margin_y=100.0,
    )

    assert 0.49 < gain < 0.51


def test_locked_matrices_are_translation_only():
    matrices = _translation_matrices(
        np.array([0.0, 10.0]),
        np.array([0.0, -5.0]),
    )

    assert np.array_equal(
        matrices[:, :2, :2],
        np.repeat(
            np.eye(2)[None, ...],
            2,
            axis=0,
        ),
    )
    assert matrices[1, 0, 2] == 10.0
    assert matrices[1, 1, 2] == -5.0
