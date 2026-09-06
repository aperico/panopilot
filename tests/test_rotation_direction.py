import math
import cv2
import numpy as np

from panopilot.attitude import rotate_equirectangular


def _rotation_y(angle_deg):
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([
        [c, 0.0, s],
        [0.0, 1.0, 0.0],
        [-s, 0.0, c],
    ], dtype=np.float64)


def test_content_rotation_moves_forward_marker_to_positive_longitude():
    # Equirectangular convention:
    # center x = longitude 0 = +Z (forward)
    # x = 3/4 width = longitude +90 deg = +X (right)
    h, w = 180, 360
    image = np.zeros((h, w, 3), dtype=np.uint8)

    # Small white patch at forward direction.
    image[h//2-2:h//2+3, w//2-2:w//2+3] = 255

    rotated = rotate_equirectangular(image, _rotation_y(90.0))

    gray = cv2.cvtColor(rotated, cv2.COLOR_BGR2GRAY)
    _minv, _maxv, _minloc, maxloc = cv2.minMaxLoc(gray)

    expected_x = int(round(0.75 * w))
    assert abs(maxloc[0] - expected_x) <= 3
