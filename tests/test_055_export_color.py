"""Decode real exports: metadata checks alone cannot detect matrix mistakes."""
import json
import shutil
import subprocess
from types import SimpleNamespace

import numpy as np
import pytest

from panopilot.project_export import _video_encoder_command
from panopilot.project_export import verify_project_export
from panopilot import project_export
from panopilot.video_encoding import SDR_VIDEO_PROPERTIES, video_encoder_command


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg and ffprobe required")
@pytest.mark.parametrize("width,height", [(256, 128), (128, 256), (1920, 1080)])
def test_export_color_pixels_and_signaling(tmp_path, width, height):
    # BGR black, white, red, green, blue, gray, and two skin-like patches.
    colors = np.array([(0, 0, 0), (255, 255, 255), (0, 0, 255),
                       (0, 255, 0), (255, 0, 0), (128, 128, 128),
                       (90, 140, 190), (60, 85, 120)], dtype=np.uint8)
    frame = np.repeat(colors, width // 8, axis=0)[None].repeat(height, axis=0)
    output = tmp_path / "color.mp4"
    subprocess.run(_video_encoder_command(output, width=width, height=height,
                   fps=30, crf=16, preset="slow"), input=frame.tobytes(),
                   capture_output=True, check=True, timeout=30)
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output)
    ], timeout=30))["streams"][0]
    assert (probe["width"], probe["height"]) == (width, height)
    assert probe["pix_fmt"] == "yuv420p"
    assert probe["color_range"] == "tv"
    for field in ("color_space", "color_transfer", "color_primaries"):
        assert probe[field] == "bt709"
    raw = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(output), "-frames:v", "1",
        "-pix_fmt", "yuv420p", "-f", "rawvideo", "pipe:1"
    ], timeout=30)
    luma = np.frombuffer(raw, np.uint8, count=width * height).reshape(height, width)
    # Independent BT.709 limited-range luma calculation, not FFmpeg as oracle.
    expected = 16 + 219 * (colors.astype(float) @ np.array([.0722, .7152, .2126])) / 255
    centers = np.arange(8) * (width // 8) + width // 16
    measured = luma[height // 2, centers].astype(float)
    assert np.max(np.abs(measured - expected)) <= 2, (measured, expected)
    rgb = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(output), "-frames:v", "1",
        "-pix_fmt", "bgr24", "-f", "rawvideo", "pipe:1"
    ], timeout=30)
    decoded = np.frombuffer(rgb, np.uint8).reshape(height, width, 3)
    error = np.abs(decoded[height // 2, centers].astype(float) - colors)
    assert error.max() <= 4, error
    verify_project_export(output, profile=SimpleNamespace(width=width, height=height, fps=30),
                          expected_frames=1, expected_duration=1 / 30, expect_audio=False)


@pytest.mark.parametrize("field", list(SDR_VIDEO_PROPERTIES))
def test_final_verification_rejects_missing_color_properties(monkeypatch, field):
    stream = dict(SDR_VIDEO_PROPERTIES, codec_type="video", codec_name="h264")
    del stream[field]
    monkeypatch.setattr(project_export, "probe_source", lambda _: {"streams": [stream]})
    with pytest.raises(RuntimeError, match=field):
        verify_project_export("unused.mp4", profile=None, expected_frames=1,
                              expected_duration=1 / 30, expect_audio=False)


def test_all_stabilization_encoders_share_delivery_policy():
    from panopilot import (visual_stabilization, locked_stabilization,
                           anchored_stabilization, extreme_stabilization)
    for module in (visual_stabilization, locked_stabilization,
                   anchored_stabilization, extreme_stabilization):
        assert module.video_encoder_command is video_encoder_command
