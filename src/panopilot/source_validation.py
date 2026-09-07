"""Source Recording acceptance gate used by Project import."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math
from pathlib import Path

from .dji import extract_calibration, extract_orientation_data
from .media_identity import source_identity
from .source import decode_lens_pair, lens_streams, probe_source


SUPPORTED_OSV_PROFILE_ID = "dji-osmo360-dual-1920-hevc-100fps-v1"
SUPPORTED_OSV_LENS_WIDTH = 1920
SUPPORTED_OSV_LENS_HEIGHT = 1920
SUPPORTED_OSV_LENS_CODEC = "hevc"
SUPPORTED_OSV_FPS = 100.0
SUPPORTED_OSV_FPS_TOLERANCE = 0.05
SUPPORTED_OSV_START_TOLERANCE_S = 0.010


def _stream_rate(stream):
    values = []

    for key in (
        "avg_frame_rate",
        "r_frame_rate",
    ):
        value = stream.get(
            key
        )

        if value in (
            None,
            "",
            "0/0",
            "N/A",
        ):
            continue

        try:
            rate = float(
                Fraction(
                    str(
                        value
                    )
                )
            )
        except (
            ValueError,
            ZeroDivisionError,
        ):
            continue

        if (
            math.isfinite(
                rate
            )
            and rate > 0.0
        ):
            values.append(
                rate
            )

    if not values:
        return None

    if len(values) >= 2:
        if abs(
            values[0]
            - values[1]
        ) > SUPPORTED_OSV_FPS_TOLERANCE:
            return None

    return float(
        sum(values)
        / len(values)
    )


def supported_osv_profile_observation(
    probe,
    lenses=None,
):
    lenses = (
        list(
            lenses
        )
        if lenses is not None
        else list(
            lens_streams(
                probe
            )
        )
    )

    observed = {
        "profile_id": (
            SUPPORTED_OSV_PROFILE_ID
        ),
        "lens_count": len(
            lenses
        ),
        "lenses": [],
    }

    for stream in lenses:
        observed[
            "lenses"
        ].append(
            {
                "index": int(
                    stream.get(
                        "index",
                        -1,
                    )
                ),
                "codec": str(
                    stream.get(
                        "codec_name"
                    )
                    or ""
                ).lower(),
                "width": int(
                    stream.get(
                        "width"
                    )
                    or 0
                ),
                "height": int(
                    stream.get(
                        "height"
                    )
                    or 0
                ),
                "fps": (
                    _stream_rate(
                        stream
                    )
                ),
                "start_time": (
                    float(
                        stream.get(
                            "start_time"
                        )
                        or 0.0
                    )
                ),
            }
        )

    return observed


def validate_supported_osv_profile(
    probe,
    lenses=None,
):
    """
    Validate the Iteration-1 empirically qualified DJI Osmo 360 profile.

    This profile is intentionally narrower than what the implementation may
    technically decode. It records what PanoPilot claims as supported rather
    than silently accepting unqualified source modes.
    """
    qualified_candidates = [
        stream
        for stream in probe.get(
            "streams",
            [],
        )
        if (
            stream.get(
                "codec_type"
            )
            == "video"
            and not stream.get(
                "disposition",
                {},
            ).get(
                "attached_pic"
            )
            and stream.get(
                "width"
            )
            and stream.get(
                "height"
            )
            and abs(
                int(
                    stream[
                        "width"
                    ]
                )
                - int(
                    stream[
                        "height"
                    ]
                )
            )
            <= 4
        )
    ]

    lenses = (
        qualified_candidates
        if lenses is None
        else list(
            lenses
        )
    )
    observed = (
        supported_osv_profile_observation(
            probe,
            lenses,
        )
    )

    if len(
        qualified_candidates
    ) != 2:
        raise RuntimeError(
            "Supported OSV profile requires exactly two panoramic lens streams"
        )

    if len(
        lenses
    ) != 2:
        raise RuntimeError(
            "Supported OSV profile requires exactly two lens streams"
        )

    for index, stream in enumerate(
        lenses,
        start=1,
    ):
        codec = str(
            stream.get(
                "codec_name"
            )
            or ""
        ).lower()
        width = int(
            stream.get(
                "width"
            )
            or 0
        )
        height = int(
            stream.get(
                "height"
            )
            or 0
        )
        rate = _stream_rate(
            stream
        )

        if codec != SUPPORTED_OSV_LENS_CODEC:
            raise RuntimeError(
                "Supported OSV profile requires HEVC lens streams; "
                f"lens {index} is {codec or 'unknown'}"
            )

        if (
            width
            != SUPPORTED_OSV_LENS_WIDTH
            or height
            != SUPPORTED_OSV_LENS_HEIGHT
        ):
            raise RuntimeError(
                "Supported OSV profile requires "
                f"{SUPPORTED_OSV_LENS_WIDTH}x{SUPPORTED_OSV_LENS_HEIGHT} "
                f"lens streams; lens {index} is {width}x{height}"
            )

        if (
            rate is None
            or abs(
                float(
                    rate
                )
                - SUPPORTED_OSV_FPS
            )
            > SUPPORTED_OSV_FPS_TOLERANCE
        ):
            raise RuntimeError(
                "Supported OSV profile requires 100 fps CFR lens streams; "
                f"lens {index} is {rate!r} fps"
            )

    starts = [
        float(
            stream.get(
                "start_time"
            )
            or 0.0
        )
        for stream in lenses
    ]

    if abs(
        starts[0]
        - starts[1]
    ) > SUPPORTED_OSV_START_TOLERANCE_S:
        raise RuntimeError(
            "Supported OSV profile requires synchronized lens starts"
        )

    return observed


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
    profile_id: str | None = None
    profile_observed: dict | None = None

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
            "profile_id": self.profile_id,
            "profile_observed": self.profile_observed,
        }


def validate_source_recording(source, *, decode_smoke=True):
    """Validate one source independently; never mutates it."""
    source = Path(source).expanduser()
    try:
        if not source.is_file():
            raise FileNotFoundError(f"File does not exist: {source}")

        if source.suffix.lower() != ".osv":
            raise RuntimeError(
                "Supported Source Recording must use the .OSV extension"
            )

        probe = probe_source(source)
        lenses = lens_streams(probe)
        if len(lenses) != 2:
            raise RuntimeError("Expected exactly two usable panoramic lens streams")

        dims = [(int(item.get("width", 0)), int(item.get("height", 0))) for item in lenses]
        if dims[0] != dims[1] or dims[0][0] <= 0 or dims[0][1] <= 0:
            raise RuntimeError(f"Lens stream dimensions are incompatible: {dims}")

        profile_observed = validate_supported_osv_profile(
            probe,
            lenses,
        )

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
            profile_id=SUPPORTED_OSV_PROFILE_ID,
            profile_observed=profile_observed,
        )
    except Exception as exc:
        return SourceAcceptance(
            source=str(source),
            accepted=False,
            reason=str(exc),
        )
