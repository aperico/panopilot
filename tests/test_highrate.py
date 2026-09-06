from panopilot.dji import build_highrate_timeline


def test_highrate_timeline_anchors_matching_quaternion_at_frame_timestamp():
    q0 = [1.0, 0.0, 0.0, 0.0]
    q1 = [0.99999, 0.0, 0.0, 0.00447]

    packets = [
        {
            "frame_index": 0,
            "timestamp_us": 1000000,
            "quat": q0,
            "highrate_quats": [
                q1,
                q0,
                q1,
                q1,
            ],
        },
        {
            "frame_index": 1,
            "timestamp_us": 1010000,
            "quat": q0,
            "highrate_quats": [
                q1,
                q0,
                q1,
                q1,
            ],
        },
    ]

    timeline, diagnostics = build_highrate_timeline(packets)

    anchored = [
        sample
        for sample in timeline
        if sample["frame_index"] == 0
        and sample["sub_index"] == 1
    ][0]

    assert abs(anchored["source_time"]) < 1e-12
    assert diagnostics["estimated_sample_period_us"] == 2500.0


def test_highrate_timeline_has_more_samples_than_packets():
    q = [1.0, 0.0, 0.0, 0.0]
    packets = [
        {
            "frame_index": 0,
            "timestamp_us": 1000000,
            "quat": q,
            "highrate_quats": [q] * 10,
        },
        {
            "frame_index": 1,
            "timestamp_us": 1010000,
            "quat": q,
            "highrate_quats": [q] * 10,
        },
    ]

    timeline, _ = build_highrate_timeline(packets)
    assert len(timeline) >= 10
