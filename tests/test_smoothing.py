import numpy as np

from panopilot.attitude import smooth_unit_vectors_centered


def _step_angles(vectors):
    dots = np.sum(vectors[:-1] * vectors[1:], axis=1)
    dots = np.clip(dots, -1.0, 1.0)
    return np.degrees(np.arccos(dots))


def test_zero_smoothing_preserves_unit_vectors():
    vectors = np.array([
        [0.0, -1.0, 0.0],
        [0.1, -0.995, 0.0],
        [-0.1, -0.995, 0.0],
    ])
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)

    out = smooth_unit_vectors_centered(vectors, 0.0)

    assert np.allclose(out, vectors)
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0)


def test_centered_smoothing_reduces_alternating_jitter():
    vectors = np.array([
        [0.10 if i % 2 == 0 else -0.10, -0.995, 0.0]
        for i in range(41)
    ], dtype=float)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)

    smoothed = smooth_unit_vectors_centered(vectors, 3.0)

    assert _step_angles(smoothed).mean() < _step_angles(vectors).mean()
    assert np.allclose(
        np.linalg.norm(smoothed, axis=1),
        1.0,
        atol=1e-9,
    )
