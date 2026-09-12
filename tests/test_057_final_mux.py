import json
import shutil
import subprocess

import numpy as np
import pytest

from panopilot.project_export import _mux_final, _video_encoder_command


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")
@pytest.mark.parametrize("frames", [12, 100])
def test_mux_preserves_reordered_video_tail_with_planned_audio(tmp_path, frames):
    video, audio, output = [tmp_path / p for p in ("video.mp4", "audio.m4a", "final.mp4")]
    frame = np.zeros((128, 256, 3), np.uint8)
    frame[:, :, 0] = np.arange(256)
    command = _video_encoder_command(video, width=256, height=128, fps=50, crf=12, preset="slow")
    command[-1:-1] = ["-bf", "3", "-b_strategy", "0"]
    subprocess.run(command, input=frame.tobytes() * frames, check=True, capture_output=True, timeout=30)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "anullsrc=r=48000:cl=stereo", "-t", str(frames / 50), "-c:a", "aac", str(audio)],
                   check=True, capture_output=True, timeout=30)
    _mux_final(video, audio, output)
    streams = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output)
    ], timeout=30))["streams"]
    v = next(s for s in streams if s["codec_type"] == "video")
    a = next(s for s in streams if s["codec_type"] == "audio")
    assert v["has_b_frames"] > 0
    assert int(v["nb_frames"]) == frames
    assert float(v["duration"]) == pytest.approx(frames / 50)
    assert abs(float(a["duration"]) - float(v["duration"])) < .05
