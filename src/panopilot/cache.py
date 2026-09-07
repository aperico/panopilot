"""
Disposable panoramic editing representation for PanoPilot.

The original OSV remains authoritative and immutable.  This cache exists only
so interactive editing can decode an already stitched/leveled panorama rather
than reconstructing the two DJI fisheye streams for every seek/playback frame.

Cache validity is derived from:
- source absolute path, size, and modification time;
- the preview profile (dimensions/fps/stabilization/audio settings).

A source/profile change naturally creates a different cache key.  Old entries
are disposable and can be removed at any time.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Optional

import cv2

from .preview import render_preview
from .source import probe_source


CACHE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PreviewProfile:
    width: int = 1280
    height: int = 640
    fps: float = 20.0
    level_horizon: bool = True
    level_strength: float = 1.0
    level_smoothing_ms: float = 100.0
    stabilization_amount: float = 0.0
    stabilization_smoothing_ms: float = 400.0
    stabilization_algorithm: str = "adaptive-highrate-v1"
    imu_source: str = "highrate"
    imu_offset_ms: float = 0.0
    with_audio: bool = True
    crf: int = 23
    preset: str = "veryfast"

    def validate(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError("preview dimensions must be positive")
        if abs(self.width / self.height - 2.0) > 0.01:
            raise ValueError("panoramic preview must use an approximately 2:1 frame")
        if self.fps <= 0:
            raise ValueError("preview fps must be greater than zero")
        if self.imu_source not in ("highrate", "perframe"):
            raise ValueError("imu_source must be 'highrate' or 'perframe'")

    def to_dict(self):
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class PreviewCacheEntry:
    cache_key: str
    video_path: Path
    metadata_path: Path
    metadata: dict
    reused: bool

    @property
    def source_duration(self):
        value = self.metadata.get("source_duration")
        return float(value) if value is not None else None

    @property
    def profile(self):
        return dict(self.metadata.get("profile", {}))

    def to_dict(self):
        return {
            "cache_key": self.cache_key,
            "video_path": str(self.video_path),
            "metadata_path": str(self.metadata_path),
            "source_duration": self.source_duration,
            "profile": self.profile,
            "reused": bool(self.reused),
        }



@dataclass(frozen=True)
class CachedSourceCandidate:
    source: Path
    source_duration: Optional[float]
    cache_key: str
    metadata_path: Path
    metadata_mtime_ns: int
    source_size: Optional[int]
    source_mtime_ns: Optional[int]
    exists: bool

    def to_dict(self):
        return {
            "source": str(self.source),
            "source_duration": (
                float(self.source_duration)
                if self.source_duration is not None
                else None
            ),
            "cache_key": self.cache_key,
            "metadata_path": str(
                self.metadata_path
            ),
            "metadata_mtime_ns": int(
                self.metadata_mtime_ns
            ),
            "source_size": (
                int(self.source_size)
                if self.source_size is not None
                else None
            ),
            "source_mtime_ns": (
                int(self.source_mtime_ns)
                if self.source_mtime_ns is not None
                else None
            ),
            "exists": bool(
                self.exists
            ),
        }


def discover_cached_sources(
    *,
    cache_dir=None,
    existing_only=False,
):
    """
    Recover source-recording references from disposable preview metadata.

    This can reconstruct source membership after a Project JSON is lost, but
    cannot reconstruct Clip order, trims, Camera Positions, or Camera Motion
    edits that were stored only in the Project.
    """
    root = (
        Path(cache_dir)
        if cache_dir is not None
        else default_cache_dir()
    )

    if not root.is_dir():
        return []

    by_source = {}

    for metadata_path in root.glob(
        "*/metadata.json"
    ):
        metadata = _read_metadata(
            metadata_path
        )

        if not metadata:
            continue

        identity = metadata.get(
            "source_identity"
        ) or {}
        raw_source = identity.get(
            "path"
        )

        if not raw_source:
            continue

        source = Path(
            raw_source
        ).expanduser()
        exists = source.is_file()

        if (
            existing_only
            and not exists
        ):
            continue

        duration = metadata.get(
            "source_duration"
        )

        try:
            duration = (
                float(duration)
                if duration is not None
                else None
            )
        except (
            TypeError,
            ValueError,
        ):
            duration = None

        try:
            metadata_mtime_ns = int(
                metadata_path.stat().st_mtime_ns
            )
        except OSError:
            metadata_mtime_ns = 0

        candidate = CachedSourceCandidate(
            source=source,
            source_duration=duration,
            cache_key=str(
                metadata.get(
                    "cache_key",
                    metadata_path.parent.name,
                )
            ),
            metadata_path=metadata_path,
            metadata_mtime_ns=(
                metadata_mtime_ns
            ),
            source_size=(
                int(
                    identity["size"]
                )
                if identity.get(
                    "size"
                ) is not None
                else None
            ),
            source_mtime_ns=(
                int(
                    identity["mtime_ns"]
                )
                if identity.get(
                    "mtime_ns"
                ) is not None
                else None
            ),
            exists=exists,
        )

        key = str(
            source.resolve(
                strict=False
            )
        )
        previous = by_source.get(
            key
        )

        # Keep the newest metadata instance for the same source path/profile
        # family. The user still chooses Clip order explicitly.
        if (
            previous is None
            or candidate.metadata_mtime_ns
            > previous.metadata_mtime_ns
        ):
            by_source[key] = candidate

    return sorted(
        by_source.values(),
        key=lambda item: (
            item.source.name.lower(),
            str(item.source).lower(),
        ),
    )


def default_cache_dir():
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "panopilot" / "preview"


def source_identity(source):
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"Source does not exist: {source}")
    stat = source.stat()
    return {
        "path": str(source.resolve()),
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def preview_cache_key(source, profile: PreviewProfile):
    payload = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "source": source_identity(source),
        "profile": profile.to_dict(),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()[:20]


def _paths(source, profile, cache_dir=None):
    key = preview_cache_key(source, profile)
    root = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    entry_dir = root / key
    return key, entry_dir / "panorama.mp4", entry_dir / "metadata.json"


def _read_metadata(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def preview_cache_is_valid(source, profile, video_path, metadata_path):
    video_path = Path(video_path)
    metadata_path = Path(metadata_path)

    if not video_path.is_file() or not metadata_path.is_file():
        return False

    metadata = _read_metadata(metadata_path)
    if not metadata:
        return False

    return (
        metadata.get("schema_version") == CACHE_SCHEMA_VERSION
        and metadata.get("source_identity") == source_identity(source)
        and metadata.get("profile") == profile.to_dict()
    )


def ensure_preview_cache(
    source,
    *,
    profile: PreviewProfile = PreviewProfile(),
    cache_dir=None,
    rebuild=False,
    progress_callback=None,
    cancel_callback=None,
):
    """
    Return a valid cached panoramic preview, preparing it when necessary.

    The cache operation itself is synchronous and transaction-safe, but callers
    may run it in a PanoPilot background job. Cooperative cancellation leaves no
    preparing media or metadata behind.
    """
    source = Path(source)
    profile.validate()

    if cancel_callback is not None and bool(cancel_callback()):
        from .jobs import JobCancelled
        raise JobCancelled("Preview preparation cancelled")

    key, video_path, metadata_path = _paths(
        source,
        profile,
        cache_dir=cache_dir,
    )

    if (
        not rebuild
        and preview_cache_is_valid(
            source,
            profile,
            video_path,
            metadata_path,
        )
    ):
        metadata = _read_metadata(metadata_path)
        return PreviewCacheEntry(
            cache_key=key,
            video_path=video_path,
            metadata_path=metadata_path,
            metadata=metadata,
            reused=True,
        )

    probe = probe_source(source)
    fmt = probe.get("format", {})
    duration_value = fmt.get("duration")

    if duration_value is None:
        raise RuntimeError("Could not determine source duration for preview preparation")

    source_duration = float(duration_value)
    if source_duration <= 0:
        raise RuntimeError("Source duration must be greater than zero")

    video_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_video = video_path.with_name("panorama.preparing.mp4")
    temporary_metadata = metadata_path.with_suffix(".json.tmp")

    temporary_video.unlink(missing_ok=True)
    temporary_metadata.unlink(missing_ok=True)

    if progress_callback:
        progress_callback(
            {
                "stage": "prepare",
                "message": "Preparing panoramic editing preview",
                "cache_key": key,
            }
        )

    try:
        summary = render_preview(
            source,
            temporary_video,
            start=0.0,
            duration=source_duration,
            fps=profile.fps,
            width=profile.width,
            height=profile.height,
            level_horizon=profile.level_horizon,
            level_strength=profile.level_strength,
            level_smoothing_ms=profile.level_smoothing_ms,
            stabilization_amount=profile.stabilization_amount,
            stabilization_smoothing_ms=profile.stabilization_smoothing_ms,
            imu_source=profile.imu_source,
            imu_offset_ms=profile.imu_offset_ms,
            use_actual_video_pts=True,
            with_audio=profile.with_audio,
            crf=profile.crf,
            preset=profile.preset,
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
        )

        metadata = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "cache_key": key,
            "source_identity": source_identity(source),
            "source_duration": source_duration,
            "profile": profile.to_dict(),
            "summary": summary,
        }

        temporary_metadata.write_text(
            json.dumps(metadata, indent=2) + "\n",
            encoding="utf-8",
        )

        temporary_video.replace(video_path)
        temporary_metadata.replace(metadata_path)

    except Exception:
        temporary_video.unlink(missing_ok=True)
        temporary_metadata.unlink(missing_ok=True)
        raise

    if progress_callback:
        progress_callback(
            {
                "stage": "ready",
                "message": "Panoramic editing preview ready",
                "cache_key": key,
                "video_path": str(video_path),
            }
        )

    return PreviewCacheEntry(
        cache_key=key,
        video_path=video_path,
        metadata_path=metadata_path,
        metadata=metadata,
        reused=False,
    )


def frame_index_for_time(source_time, fps, frame_count):
    if frame_count <= 0:
        raise ValueError("frame_count must be positive")
    if fps <= 0:
        raise ValueError("fps must be positive")

    index = int(round(max(0.0, float(source_time)) * float(fps)))
    return max(0, min(int(frame_count) - 1, index))


class PanoramaCacheReader:
    """Low-latency random/sequential reader for the cached panorama video."""

    def __init__(self, entry: PreviewCacheEntry):
        self.entry = entry
        self.capture = cv2.VideoCapture(str(entry.video_path))

        if not self.capture.isOpened():
            raise RuntimeError(
                f"Could not open panoramic editing preview: {entry.video_path}"
            )

        profile_fps = float(entry.profile.get("fps", 0.0) or 0.0)
        capture_fps = float(self.capture.get(cv2.CAP_PROP_FPS) or 0.0)
        self.fps = capture_fps if capture_fps > 0.0 else profile_fps

        if self.fps <= 0.0:
            self.capture.release()
            raise RuntimeError("Cached panorama has no usable frame rate")

        self.frame_count = int(
            round(self.capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        )
        if self.frame_count <= 0:
            self.capture.release()
            raise RuntimeError("Cached panorama has no readable frames")

        self.width = int(
            round(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0.0)
        )
        self.height = int(
            round(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0.0)
        )

        self._last_index: Optional[int] = None
        self._last_frame = None

    @property
    def media_duration(self):
        return self.frame_count / self.fps

    def read_at(self, source_time):
        target = frame_index_for_time(
            source_time,
            self.fps,
            self.frame_count,
        )

        if target == self._last_index and self._last_frame is not None:
            return self._last_frame.copy(), target / self.fps, target

        # Sequential playback normally advances by one frame. Avoid seeking in
        # that case because H.264 random seeks can be much more expensive than
        # simply decoding the next frame.
        if (
            self._last_index is not None
            and target > self._last_index
            and target - self._last_index <= 4
        ):
            frame = None
            for index in range(self._last_index + 1, target + 1):
                ok, candidate = self.capture.read()
                if not ok or candidate is None:
                    frame = None
                    break
                frame = candidate
                self._last_index = index

            if frame is not None:
                self._last_frame = frame
                return frame.copy(), target / self.fps, target

        self.capture.set(cv2.CAP_PROP_POS_FRAMES, float(target))
        ok, frame = self.capture.read()

        if not ok or frame is None:
            raise RuntimeError(
                f"Could not decode cached panorama frame {target}"
            )

        self._last_index = target
        self._last_frame = frame
        return frame.copy(), target / self.fps, target

    def close(self):
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
