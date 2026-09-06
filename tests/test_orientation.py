from panopilot.dji import orientation_from_samples


def test_orientation_interpolation_uses_source_time():
    samples = [
        {
            "source_time": 0.0,
            "frame_index": 0,
            "quat": [1.0, 0.0, 0.0, 0.0],
            "accel": [0.0, 0.0, -1.0],
        },
        {
            "source_time": 1.0,
            "frame_index": 100,
            "quat": [0.9238795325, 0.0, 0.0, 0.3826834324],
            "accel": [0.0, 0.0, -1.0],
        },
    ]

    result = orientation_from_samples(samples, 0.5)

    assert result["interpolated"] is True
    assert abs(result["alpha"] - 0.5) < 1e-9
