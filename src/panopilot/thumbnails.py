"""Disposable thumbnail helpers built from the existing panoramic preview cache.

Thumbnails are presentation artifacts only. They never become Project state and can
be deleted at any time. Using the already-prepared preview avoids reopening or
decoding original DJI dual-lens media in the GUI path.
"""
from __future__ import annotations

from pathlib import Path
import math

import cv2
import numpy as np


def thumbnail_path_for_video(video_path) -> Path:
    path = Path(video_path)
    return path.with_name(path.stem + ".thumb.jpg")


def _fit_frame(frame, width: int, height: int):
    if frame is None or frame.size == 0:
        return None
    target_w = max(16, int(width))
    target_h = max(16, int(height))
    h, w = frame.shape[:2]
    if w <= 0 or h <= 0:
        return None

    scale = max(target_w / float(w), target_h / float(h))
    resized = cv2.resize(
        frame,
        (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
        interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR,
    )
    rh, rw = resized.shape[:2]
    x0 = max(0, (rw - target_w) // 2)
    y0 = max(0, (rh - target_h) // 2)
    return resized[y0:y0 + target_h, x0:x0 + target_w].copy()



def filmstrip_tile_geometry(available_width, *, height=46, aspect=16 / 9, max_tiles=24):
    """Return a responsive thumbnail count and tile size for a timeline filmstrip.

    Filmstrip thumbnails are discrete images, never a single image stretched to
    the timeline width.  The requested height drives a natural aspect-preserving
    tile width.  The final tile width may be slightly wider so the integer number
    of tiles fills the available row; callers should crop an aspect-preserved
    pixmap to that rectangle rather than scale it non-uniformly.
    """
    width = max(1, int(available_width))
    tile_h = max(24, int(height))
    natural_w = max(32, int(round(tile_h * float(aspect))))
    count = max(1, int(math.ceil(width / float(natural_w))))
    count = min(max(1, int(max_tiles)), count)
    tile_w = max(32, int(math.ceil(width / float(count))))
    return {"count": count, "width": tile_w, "height": tile_h}


def read_video_frame(video_path, *, fraction=0.20):
    """Read one representative frame from a disposable preview video."""
    cap = cv2.VideoCapture(str(video_path))
    try:
        if not cap.isOpened():
            return None
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if frame_count > 1:
            target = int(round(max(0.0, min(1.0, float(fraction))) * (frame_count - 1)))
            cap.set(cv2.CAP_PROP_POS_FRAMES, target)
        ok, frame = cap.read()
        return frame if ok else None
    finally:
        cap.release()


def ensure_video_thumbnail(video_path, *, width=160, height=90, fraction=0.20) -> Path | None:
    """Create/reuse a compact thumbnail next to the disposable preview cache."""
    video_path = Path(video_path)
    output = thumbnail_path_for_video(video_path)
    try:
        if output.is_file() and output.stat().st_mtime_ns >= video_path.stat().st_mtime_ns:
            return output
    except OSError:
        pass

    frame = read_video_frame(video_path, fraction=fraction)
    fitted = _fit_frame(frame, width, height)
    if fitted is None:
        return None
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), fitted, [int(cv2.IMWRITE_JPEG_QUALITY), 82]):
        return None
    return output


def sample_video_thumbnails(video_path, *, count=8, width=160, height=90):
    """Return representative BGR thumbnail frames across the cached source.

    Intended for the Trim timeline. The caller decides how to display the frames;
    no Qt dependency is introduced here.
    """
    count = max(1, int(count))
    cap = cv2.VideoCapture(str(video_path))
    frames = []
    try:
        if not cap.isOpened():
            return frames
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if frame_count <= 0:
            return frames
        positions = np.linspace(0, max(0, frame_count - 1), count)
        for position in positions:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(float(position))))
            ok, frame = cap.read()
            if not ok:
                continue
            fitted = _fit_frame(frame, width, height)
            if fitted is not None:
                frames.append(fitted)
        return frames
    finally:
        cap.release()


def sample_video_thumbnails_range(
    video_path,
    *,
    start_time=0.0,
    end_time=None,
    count=8,
    width=160,
    height=90,
):
    """Return aspect-preserved representative frames for one visible time range.

    The cached panoramic preview is the source.  This is intended for timeline
    navigation when the visible window is zoomed or panned: thumbnail density
    follows the visible interval instead of stretching a fixed set of images.
    """
    count = max(1, int(count))
    cap = cv2.VideoCapture(str(video_path))
    frames = []
    try:
        if not cap.isOpened():
            return frames
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if fps <= 0.0 or frame_count <= 0:
            return frames
        media_duration = max(0.0, (frame_count - 1) / fps)
        start = max(0.0, min(float(start_time), media_duration))
        end = media_duration if end_time is None else max(start, min(float(end_time), media_duration))
        if count == 1:
            times = [(start + end) / 2.0]
        else:
            times = np.linspace(start, end, count)
        for source_time in times:
            frame_index = max(0, min(frame_count - 1, int(round(float(source_time) * fps))))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            fitted = _fit_frame(frame, width, height)
            if fitted is not None:
                frames.append({
                    "source_time": float(frame_index / fps),
                    "frame": fitted,
                })
        return frames
    finally:
        cap.release()
