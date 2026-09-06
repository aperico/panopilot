from panopilot.dji import decode_calibration


def test_empty_payload_has_no_lenses():
    result = decode_calibration(b"")
    assert result["lenses"] == []
