"""Source Recording acceptance gate used by Project import."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .dji import extract_calibration, extract_orientation_data
from .media_identity import source_identity
from .source import decode_lens_pair, lens_streams, probe_source


@dataclass(frozen=True)
class SourceAcceptance:
    source: str
    accepted: bool
    reason: str
    identity: dict | None = None
    duration: float | None = None
    lens_stream_indexes: tuple = ()
    lens_dimensions: tuple | None = None
    orientation_packets: int | None = None

    def to_dict(self):
        return {
            "source": self.source,
            "accepted": bool(self.accepted),
            "reason": str(self.reason),
            "identity": self.identity,
            "duration": self.duration,
            "lens_stream_indexes": list(self.lens_stream_indexes),
            "lens_dimensions": list(self.lens_dimensions) if self.lens_dimensions else None,
            "orientation_packets": self.orientation_packets,
        }


def validate_source_recording(source, *, decode_smoke=True):
    """Validate one source independently; never mutates it."""
    source = Path(source).expanduser()
    try:
        if not source.is_file():
            raise FileNotFoundError(f"File does not exist: {source}")

        probe = probe_source(source)
        lenses = lens_streams(probe)
        if len(lenses) != 2:
            raise RuntimeError("Expected exactly two usable panoramic lens streams")

        dims = [(int(item.get("width", 0)), int(item.get("height", 0))) for item in lenses]
        if dims[0] != dims[1] or dims[0][0] <= 0 or dims[0][1] <= 0:
            raise RuntimeError(f"Lens stream dimensions are incompatible: {dims}")

        duration_value = probe.get("format", {}).get("duration")
        if duration_value is None or float(duration_value) <= 0.0:
            raise RuntimeError("Source duration is unavailable or invalid")
        duration = float(duration_value)

        calibration = extract_calibration(source)
        if len(calibration.get("lenses", [])) < 2:
            raise RuntimeError("DJI factory lens calibration is incomplete")

        orientation = extract_orientation_data(source)
        perframe = orientation.get("perframe") or []
        if not perframe:
            raise RuntimeError("DJI orientation metadata is unavailable")

        if decode_smoke:
            # Decode close to the beginning but not exactly at a possible
            # container edge. This proves the installed FFmpeg can decode both
            # accepted lens streams without creating derived media.
            smoke_time = min(max(0.0, duration * 0.02), max(0.0, duration - 0.001))
            frame0, frame1, _ = decode_lens_pair(source, source_time=smoke_time, probe=probe)
            if frame0.shape[:2] != frame1.shape[:2]:
                raise RuntimeError("Decoded lens frames do not have matching dimensions")

        identity = source_identity(source)
        return SourceAcceptance(
            source=str(source),
            accepted=True,
            reason="supported",
            identity=identity,
            duration=duration,
            lens_stream_indexes=tuple(int(item["index"]) for item in lenses),
            lens_dimensions=dims[0],
            orientation_packets=len(perframe),
        )
    except Exception as exc:
        return SourceAcceptance(
            source=str(source),
            accepted=False,
            reason=str(exc),
        )
