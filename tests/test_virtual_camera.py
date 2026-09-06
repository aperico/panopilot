import cv2
import numpy as np
import pytest

from panopilot.virtual_camera import (
    VirtualCamera,
    aspect_dimensions,
    equirectangular_map,
    reframe_equirectangular,
)


def test_aspect_defaults():
    assert aspect_dimensions("16:9") == (1920, 1080)
    assert aspect_dimensions("9:16") == (1080, 1920)


def test_aspect_derives_missing_dimension():
    assert aspect_dimensions("16:9", width=1280) == (1280, 720)
    assert aspect_dimensions("9:16", height=1280) == (720, 1280)


def test_bad_aspect_dimensions_rejected():
    with pytest.raises(ValueError):
        aspect_dimensions("16:9", width=1000, height=1000)


def test_center_ray_at_zero_camera_maps_near_panorama_center():
    pano_w, pano_h = 3600, 1800
    out_w, out_h = 101, 101

    mx, my = equirectangular_map(
        pano_w,
        pano_h,
        out_w,
        out_h,
        VirtualCamera(yaw_deg=0, pitch_deg=0, fov_deg=90),
    )

    x = float(mx[out_h // 2, out_w // 2])
    y = float(my[out_h // 2, out_w // 2])

    assert abs(x - (pano_w / 2 - 0.5)) < 1.0
    assert abs(y - (pano_h / 2 - 0.5)) < 1.0


def test_positive_90_yaw_looks_right():
    pano_w, pano_h = 3600, 1800

    mx, my = equirectangular_map(
        pano_w,
        pano_h,
        101,
        101,
        VirtualCamera(yaw_deg=90, pitch_deg=0, fov_deg=90),
    )

    x = float(mx[50, 50])
    assert abs(x - (0.75 * pano_w - 0.5)) < 2.0


def test_positive_pitch_looks_up():
    pano_w, pano_h = 3600, 1800

    mx, my = equirectangular_map(
        pano_w,
        pano_h,
        101,
        101,
        VirtualCamera(yaw_deg=0, pitch_deg=30, fov_deg=90),
    )

    y = float(my[50, 50])
    expected = ((90.0 - 30.0) / 180.0) * pano_h - 0.5

    assert abs(y - expected) < 2.0


def test_reframe_output_shape():
    panorama = np.zeros((360, 720, 3), dtype=np.uint8)

    out = reframe_equirectangular(
        panorama,
        VirtualCamera(),
        320,
        180,
    )

    assert out.shape == (180, 320, 3)
