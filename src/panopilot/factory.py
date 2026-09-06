from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
import json

import cv2
import numpy as np


YAW_OFFSET_DEG = 90.0
FOV_HALF_DEG = 96.0
FADE_HALF_DEG = 5.0
THETA_LIN_DEG = 85.0


def quat_to_rot(q):
    w, x, y, z = [float(v) for v in q]
    n = math.sqrt(w*w + x*x + y*y + z*z)
    if n < 1e-12:
        raise ValueError("Invalid zero-length quaternion")
    w, x, y, z = w/n, x/n, y/n, z/n
    return np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - w*z),     2*(x*z + w*y)],
        [2*(x*y + w*z),     1 - 2*(x*x + z*z), 2*(y*z - w*x)],
        [2*(x*z - w*y),     2*(y*z + w*x),     1 - 2*(x*x + y*y)],
    ], dtype=np.float64)


def scale_lens_calibration(lens: dict, src_w: int, src_h: int) -> dict:
    """
    Scale factory calibration coordinates to the actual decoded stream size.

    The uploaded Osmo 360 calibration is defined for 3840x3840 while the tested
    100-fps video streams decode as 1920x1920. Using the factory coordinates
    without scaling addresses the wrong pixels.

    Extrinsic orientation and distortion coefficients are dimensionless and
    are therefore not scaled.
    """
    cal_w = float(lens["width"])
    cal_h = float(lens["height"])
    sx = float(src_w) / cal_w
    sy = float(src_h) / cal_h

    out = dict(lens)
    out["fx"] = float(lens["fx"]) * sx
    out["fy"] = float(lens["fy"]) * sy
    out["cx"] = float(lens["cx"]) * sx
    out["cy"] = float(lens["cy"]) * sy
    out["width"] = float(src_w)
    out["height"] = float(src_h)

    if lens.get("radial_lut_1"):
        out["radial_lut_1"] = [float(v) * sx for v in lens["radial_lut_1"]]
    if lens.get("radial_lut_2"):
        out["radial_lut_2"] = [float(v) * sy for v in lens["radial_lut_2"]]

    out["_scale_x"] = sx
    out["_scale_y"] = sy
    return out


def radial_model(lens: dict):
    fx = float(lens["fx"])
    k1, k2, k3, k4 = (float(k) for k in lens["dist"])
    t0 = math.radians(THETA_LIN_DEG)

    def g(t):
        return t + k1*t**3 + k2*t**5 + k3*t**7 + k4*t**9

    def gprime(t):
        return 1 + 3*k1*t**2 + 5*k2*t**4 + 7*k3*t**6 + 9*k4*t**8

    g0 = g(t0)
    gp0 = gprime(t0)

    def gext(t):
        return np.where(t <= t0, g(t), g0 + gp0*(t-t0))

    scale = 1.0
    lut1 = lens.get("radial_lut_1")
    lut2 = lens.get("radial_lut_2")
    if lut1 and lut2 and len(lut1) >= 14 and len(lut2) >= 14:
        x = np.asarray(lut1[1:], dtype=float)
        y = np.asarray(lut2[1:], dtype=float)
        radii = np.hypot(x - float(lens["cx"]), y - float(lens["cy"]))
        r90 = fx * float(gext(np.pi/2))
        if r90 > 1e-9:
            scale = float(radii.mean()) / r90

    return lambda theta: scale * fx * gext(theta), scale


@dataclass
class MapDiagnostics:
    source_width: int
    source_height: int
    calibration_width: float
    calibration_height: float
    scale_x: float
    scale_y: float
    radial_scale_lens0: float
    radial_scale_lens1: float


class FactoryCalibratedMapper:
    """
    DJI factory-calibrated dual-fisheye -> equirectangular mapper.

    Output convention follows the calibration/body-frame geometry used by
    PanoForge's validated map generator:
      body X = right
      body Y = forward
      body Z = vertical axis
      plus a +90 degree longitude offset to align the panoramic baseline.
    """

    def __init__(self, calibration: dict, src_w: int, src_h: int,
                 out_w: int = 1920, out_h: int = 960):
        if len(calibration.get("lenses", [])) < 2:
            raise ValueError("Calibration must contain at least two lens blocks")

        raw0 = calibration["lenses"][0]
        raw1 = calibration["lenses"][1]
        self.lens0 = scale_lens_calibration(raw0, src_w, src_h)
        self.lens1 = scale_lens_calibration(raw1, src_w, src_h)
        self.out_w = int(out_w)
        self.out_h = int(out_h)

        self.map0_x, self.map0_y, self.w0, rs0 = self._build_map(self.lens0)
        self.map1_x, self.map1_y, self.w1, rs1 = self._build_map(self.lens1)

        total = self.w0 + self.w1
        self.uncovered = total <= 1e-9
        total = np.where(self.uncovered, 1.0, total)
        self.w0 = (self.w0 / total).astype(np.float32)
        self.w1 = (self.w1 / total).astype(np.float32)

        self.diagnostics = MapDiagnostics(
            source_width=src_w,
            source_height=src_h,
            calibration_width=float(raw0["width"]),
            calibration_height=float(raw0["height"]),
            scale_x=float(self.lens0["_scale_x"]),
            scale_y=float(self.lens0["_scale_y"]),
            radial_scale_lens0=float(rs0),
            radial_scale_lens1=float(rs1),
        )

    def _body_directions(self):
        lon = ((np.arange(self.out_w, dtype=np.float64) + 0.5)
               / self.out_w * 2*np.pi - np.pi
               + math.radians(YAW_OFFSET_DEG))
        lat = np.pi/2 - (
            (np.arange(self.out_h, dtype=np.float64) + 0.5)
            / self.out_h * np.pi
        )

        cl = np.cos(lat)[:, None]
        sl = np.sin(lat)[:, None]

        return np.stack([
            cl * np.sin(lon)[None, :],
            cl * np.cos(lon)[None, :],
            np.broadcast_to(sl, (self.out_h, self.out_w)),
        ], axis=-1)

    def _build_map(self, lens):
        d = self._body_directions()
        R = quat_to_rot(lens["extrinsic_quat"])
        dl = d @ R.T

        theta = np.arccos(np.clip(dl[..., 2], -1.0, 1.0))
        rho = np.hypot(dl[..., 0], dl[..., 1])
        rho = np.maximum(rho, 1e-12)

        rfun, radial_scale = radial_model(lens)
        rr = rfun(theta)

        px = float(lens["cx"]) + rr * dl[..., 0] / rho
        py = float(lens["cy"]) + rr * dl[..., 1] / rho

        theta_max = math.radians(FOV_HALF_DEG)
        valid = (
            (theta < theta_max)
            & (px >= 0) & (px <= float(lens["width"]) - 1)
            & (py >= 0) & (py <= float(lens["height"]) - 1)
        )

        # Soft overlap weighting around the 90-degree seam.
        a0 = math.radians(90.0 - FADE_HALF_DEG)
        a1 = math.radians(90.0 + FADE_HALF_DEG)
        weight = np.clip((a1 - theta) / (a1 - a0), 0.0, 1.0)
        weight = np.where(valid, weight, 0.0).astype(np.float32)

        mx = np.where(valid, px, -1).astype(np.float32)
        my = np.where(valid, py, -1).astype(np.float32)
        return mx, my, weight, radial_scale

    def stitch(self, frame0, frame1):
        p0 = cv2.remap(
            frame0,
            self.map0_x,
            self.map0_y,
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
        )
        p1 = cv2.remap(
            frame1,
            self.map1_x,
            self.map1_y,
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
        )

        # The weights are already normalized per output pixel. OpenCV's
        # blendLinear performs the same spatially varying weighted blend in
        # optimized native code, avoiding two full float32 image conversions
        # plus large NumPy temporaries for every panorama frame.
        out = cv2.blendLinear(
            p0,
            p1,
            self.w0,
            self.w1,
        )
        out[self.uncovered] = 0
        return out


def load_calibration(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
