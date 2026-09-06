import json
from pathlib import Path
from panopilot.factory import scale_lens_calibration


def test_calibration_scaling():
    lens = {
        "fx": 1040.0, "fy": 1050.0,
        "cx": 1920.0, "cy": 1920.0,
        "width": 3840.0, "height": 3840.0,
        "dist": [0,0,0,0],
        "extrinsic_quat": [1,0,0,0],
        "radial_lut_1": [1920.0, 3200.0],
        "radial_lut_2": [1920.0, 2800.0],
    }
    s = scale_lens_calibration(lens, 1920, 1920)
    assert s["fx"] == 520.0
    assert s["cx"] == 960.0
    assert s["radial_lut_1"][1] == 1600.0
    assert s["_scale_x"] == 0.5
