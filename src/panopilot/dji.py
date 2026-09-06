"""
DJI Osmo 360 djmd metadata access.

The reverse-engineered field interpretation is based on PanoForge's
MIT-licensed DJI metadata work. It remains isolated behind this module so the
PanoPilot editing/reframing domain does not depend on DJI internals.

0.9.0 adds the ~1 kHz quaternion stream and aligns it to the per-frame DJI
timestamp using the per-frame quaternion as an anchor.
"""
from __future__ import annotations

import mmap
import math
import statistics
import struct
from pathlib import Path

from .mp4parse import tracks


def _read_varint(data, index):
    shift = 0
    value = 0

    while True:
        byte = data[index]
        index += 1
        value |= (byte & 0x7F) << shift

        if not byte & 0x80:
            return value, index

        shift += 7


def _parse_fields(data):
    index = 0
    n = len(data)
    out = {}

    while index < n:
        try:
            tag, index = _read_varint(data, index)
        except (IndexError, ValueError):
            break

        field_number = tag >> 3
        wire_type = tag & 7

        if wire_type == 0:
            value, index = _read_varint(data, index)

        elif wire_type == 5:
            if index + 4 > n:
                break
            value = data[index:index + 4]
            index += 4

        elif wire_type == 1:
            if index + 8 > n:
                break
            value = data[index:index + 8]
            index += 8

        elif wire_type == 2:
            length, index = _read_varint(data, index)
            if index + length > n:
                break
            value = data[index:index + length]
            index += length

        else:
            break

        out.setdefault(field_number, []).append((wire_type, value))

    return out


def _f32(value):
    return struct.unpack("<f", value)[0]


def _floats(value):
    if len(value) % 4:
        return []
    return list(struct.unpack(f"<{len(value) // 4}f", value))


def _subfloats(data, keys):
    fields = _parse_fields(data)
    return [
        _f32(fields[key][0][1]) if key in fields else None
        for key in keys
    ]


def _normalize_quat(q):
    n = math.sqrt(sum(float(value) ** 2 for value in q))
    if n < 1e-12:
        raise ValueError("Zero-length DJI orientation quaternion")
    return [float(value) / n for value in q]


def _quat_dot(a, b):
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _quat_angle_deg(a, b):
    dot = abs(_quat_dot(_normalize_quat(a), _normalize_quat(b)))
    dot = max(-1.0, min(1.0, dot))
    return 2.0 * math.degrees(math.acos(dot))


def _slerp(q0, q1, alpha):
    q0 = _normalize_quat(q0)
    q1 = _normalize_quat(q1)

    dot = _quat_dot(q0, q1)

    if dot < 0.0:
        q1 = [-value for value in q1]
        dot = -dot

    dot = max(-1.0, min(1.0, dot))

    if dot > 0.9995:
        result = [
            q0[i] + alpha * (q1[i] - q0[i])
            for i in range(4)
        ]
        return _normalize_quat(result)

    theta0 = math.acos(dot)
    sin_theta0 = math.sin(theta0)
    theta = theta0 * alpha

    s0 = math.sin(theta0 - theta) / sin_theta0
    s1 = math.sin(theta) / sin_theta0

    return [
        s0 * q0[i] + s1 * q1[i]
        for i in range(4)
    ]


def _find_full_djmd_track(track_list):
    candidates = []

    for track in track_list:
        if track["codec"] == b"djmd" and track["samples"]:
            first_sample_size = track["samples"][0][1]
            candidates.append((first_sample_size, track))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1] if candidates else None


def decode_calibration(first_sample):
    top = _parse_fields(first_sample)
    result = {"lenses": []}

    if 1 in top:
        header = _parse_fields(top[1][0][1])
        device = _parse_fields(header[1][0][1]) if 1 in header else {}

        def text_field(key):
            if key in device and device[key][0][0] == 2:
                return device[key][0][1].decode("utf-8", "replace")
            return None

        result["proto"] = text_field(1)
        result["fw_a"] = text_field(2)
        result["proto_ver"] = text_field(3)
        result["serial"] = text_field(5)
        result["fw_b"] = text_field(6)
        result["model"] = text_field(10)

        if 3 in header:
            quaternion = _parse_fields(header[3][0][1])
            if 1 in quaternion:
                result["initial_quat"] = _floats(quaternion[1][0][1])

    if 2 in top:
        block = _parse_fields(top[2][0][1])

        if 6 in block:
            calibration = _parse_fields(block[6][0][1])

            for field_number in sorted(calibration):
                for wire_type, value in calibration[field_number]:
                    if wire_type != 2:
                        continue

                    lens_payload = _parse_fields(value)
                    if 1 not in lens_payload:
                        continue

                    def number(key):
                        return (
                            _f32(lens_payload[key][0][1])
                            if key in lens_payload
                            else None
                        )

                    lens = {
                        "fx": number(1),
                        "fy": number(2),
                        "cx": number(3),
                        "cy": number(4),
                        "dist": [number(k) for k in (5, 6, 7, 8)],
                        "width": number(10),
                        "height": number(11),
                        "yaw_deg": number(12),
                        "pitch_deg": number(13),
                    }

                    if 21 in lens_payload:
                        lens["extrinsic_quat"] = _floats(
                            lens_payload[21][0][1]
                        )

                    if 22 in lens_payload:
                        lens["radial_lut_1"] = _floats(
                            lens_payload[22][0][1]
                        )

                    if 23 in lens_payload:
                        lens["radial_lut_2"] = _floats(
                            lens_payload[23][0][1]
                        )

                    result["lenses"].append(lens)

    return result


def decode_orientation_packet(sample):
    """
    Decode one djmd packet.

    Returns:
      {
        timestamp_us,
        quat,              # per-frame quaternion
        accel,
        highrate_quats,    # approximately 1 kHz
        highrate_block_timestamp
      }

    The high-rate block timestamp is preserved when present, but 0.9.0 uses the
    per-frame quaternion/timestamp as the primary exposure-time anchor because
    the exact semantics of the block timestamp are still reverse-engineered.
    """
    top = _parse_fields(sample)

    if 3 not in top:
        return None

    inner = _parse_fields(top[3][0][1])
    result = {
        "highrate_quats": [],
        "highrate_block_timestamp": None,
    }

    if 1 in inner:
        header = _parse_fields(inner[1][0][1])
        if 2 in header and header[2][0][0] == 0:
            result["timestamp_us"] = int(header[2][0][1])

    if 2 in inner:
        motion = _parse_fields(inner[2][0][1])

        if 9 in motion:
            quat = _subfloats(motion[9][0][1], (1, 2, 3, 4))
            if all(value is not None for value in quat):
                result["quat"] = _normalize_quat(quat)

        if 10 in motion:
            accel = _subfloats(motion[10][0][1], (2, 3, 4))
            if all(value is not None for value in accel):
                result["accel"] = [float(value) for value in accel]

    if 3 in inner:
        level1 = _parse_fields(inner[3][0][1])

        if 2 in level1:
            level2 = _parse_fields(level1[2][0][1])

            if 1 in level2:
                block = _parse_fields(level2[1][0][1])

                if 1 in block and block[1][0][0] == 0:
                    result["highrate_block_timestamp"] = int(
                        block[1][0][1]
                    )

                for wire_type, value in block.get(3, []):
                    if wire_type != 2:
                        continue

                    quat = _subfloats(value, (1, 2, 3, 4))

                    if all(component is not None for component in quat):
                        result["highrate_quats"].append(
                            _normalize_quat(quat)
                        )

    return result if result.get("quat") else None


def _metadata(osv_path):
    path = Path(osv_path)

    with path.open("rb") as fp:
        with mmap.mmap(fp.fileno(), length=0, access=mmap.ACCESS_READ) as data:
            track_list = tracks(data)
            djmd = _find_full_djmd_track(track_list)

            if not djmd:
                raise RuntimeError(
                    "No usable DJI djmd metadata track was found in the OSV"
                )

            samples = list(djmd["samples"])
            first_offset, first_size = samples[0]

            calibration = decode_calibration(
                data[first_offset:first_offset + first_size]
            )

            packets = []

            for frame_index, (offset, size) in enumerate(samples):
                decoded = decode_orientation_packet(
                    data[offset:offset + size]
                )

                if decoded is None:
                    continue

                decoded["frame_index"] = frame_index
                packets.append(decoded)

    return calibration, packets


def extract_calibration(osv_path):
    calibration, _packets = _metadata(osv_path)

    if len(calibration.get("lenses", [])) < 2:
        raise RuntimeError(
            "DJI metadata was found, but fewer than two usable lens "
            "calibration blocks were decoded"
        )

    return calibration


def _perframe_samples_from_packets(packets):
    if not packets:
        return []

    timestamped = [
        packet for packet in packets
        if packet.get("timestamp_us") is not None
    ]

    t0 = timestamped[0]["timestamp_us"] if timestamped else None
    samples = []

    for packet in packets:
        sample = {
            "frame_index": packet["frame_index"],
            "timestamp_us": packet.get("timestamp_us"),
            "quat": packet["quat"],
            "accel": packet.get("accel"),
            "source": "perframe",
        }

        if t0 is not None and packet.get("timestamp_us") is not None:
            sample["source_time"] = (
                packet["timestamp_us"] - t0
            ) * 1e-6

        samples.append(sample)

    return samples


def _nearest_highrate_anchor_index(perframe_quat, highrate_quats):
    if not highrate_quats:
        return None, None

    best_index = 0
    best_angle = float("inf")

    for index, quat in enumerate(highrate_quats):
        angle = _quat_angle_deg(perframe_quat, quat)

        if angle < best_angle:
            best_angle = angle
            best_index = index

    return best_index, best_angle


def build_highrate_timeline(packets):
    """
    Build an exposure-time-aligned ~1 kHz quaternion timeline.

    Key empirical fact from the current Osmo 360 source:
    the per-frame quaternion is copied from one of the high-rate quaternion
    samples in the same packet. The matching sub-index varies from packet to
    packet.

    We therefore:
      1. find the high-rate quaternion that best matches the per-frame quat;
      2. anchor that high-rate sample at the per-frame DJI timestamp;
      3. estimate the high-rate sample period from the median video-packet
         timestamp interval divided by the median high-rate count;
      4. place neighboring high-rate samples before/after that anchor.

    This is materially better than assuming high-rate sub-index zero coincides
    with video exposure time.
    """
    usable = [
        packet for packet in packets
        if packet.get("timestamp_us") is not None
        and packet.get("quat")
        and packet.get("highrate_quats")
    ]

    if not usable:
        return [], {
            "sample_count": 0,
            "anchor_match_mean_deg": None,
            "anchor_match_max_deg": None,
            "estimated_sample_period_us": None,
        }

    frame_intervals = []

    for a, b in zip(usable[:-1], usable[1:]):
        delta = b["timestamp_us"] - a["timestamp_us"]
        if delta > 0:
            frame_intervals.append(float(delta))

    counts = [
        len(packet["highrate_quats"])
        for packet in usable
        if packet["highrate_quats"]
    ]

    median_frame_interval_us = (
        statistics.median(frame_intervals)
        if frame_intervals
        else 10000.0
    )

    median_samples_per_packet = (
        statistics.median(counts)
        if counts
        else 10.0
    )

    estimated_sample_period_us = (
        median_frame_interval_us
        / max(1.0, float(median_samples_per_packet))
    )

    t0 = usable[0]["timestamp_us"]
    samples = []
    anchor_errors = []

    for packet in usable:
        anchor_index, anchor_error = _nearest_highrate_anchor_index(
            packet["quat"],
            packet["highrate_quats"],
        )

        if anchor_index is None:
            continue

        anchor_errors.append(float(anchor_error))

        for sub_index, quat in enumerate(packet["highrate_quats"]):
            timestamp_us = (
                float(packet["timestamp_us"])
                + (sub_index - anchor_index) * estimated_sample_period_us
            )

            samples.append({
                "frame_index": packet["frame_index"],
                "sub_index": sub_index,
                "timestamp_us": float(timestamp_us),
                "source_time": (float(timestamp_us) - float(t0)) * 1e-6,
                "quat": quat,
                "source": "highrate",
                "anchor_index": int(anchor_index),
                "anchor_match_deg": float(anchor_error),
            })

    samples.sort(key=lambda sample: sample["source_time"])

    # Remove exact/near duplicate times while preserving the later item.
    deduped = []

    for sample in samples:
        if (
            deduped
            and abs(
                sample["source_time"] - deduped[-1]["source_time"]
            ) < 1e-9
        ):
            deduped[-1] = sample
        else:
            deduped.append(sample)

    diagnostics = {
        "sample_count": len(deduped),
        "packet_count": len(usable),
        "median_samples_per_packet": float(median_samples_per_packet),
        "median_frame_interval_us": float(median_frame_interval_us),
        "estimated_sample_period_us": float(estimated_sample_period_us),
        "anchor_match_mean_deg": (
            sum(anchor_errors) / len(anchor_errors)
            if anchor_errors
            else None
        ),
        "anchor_match_max_deg": (
            max(anchor_errors)
            if anchor_errors
            else None
        ),
    }

    return deduped, diagnostics


def extract_orientation_data(osv_path):
    _calibration, packets = _metadata(osv_path)

    if not packets:
        raise RuntimeError(
            "DJI metadata was found, but no usable orientation packets "
            "were decoded"
        )

    perframe = _perframe_samples_from_packets(packets)
    highrate, diagnostics = build_highrate_timeline(packets)

    return {
        "perframe": perframe,
        "highrate": highrate,
        "highrate_diagnostics": diagnostics,
    }


def extract_orientation_samples(osv_path, source="highrate"):
    data = extract_orientation_data(osv_path)

    if source == "highrate" and data["highrate"]:
        return data["highrate"]

    if source in ("perframe", "highrate"):
        return data["perframe"]

    raise ValueError(
        f"Unsupported IMU source {source!r}; expected 'highrate' or 'perframe'"
    )


def orientation_from_samples(samples, source_time):
    """
    Interpolate a previously loaded DJI orientation series at one Source Time.
    """
    if not samples:
        raise RuntimeError("No DJI orientation samples are available")

    target = float(source_time)

    timed = [
        sample for sample in samples
        if sample.get("source_time") is not None
    ]

    if not timed:
        index = max(0, min(len(samples) - 1, int(round(target))))
        return {
            **samples[index],
            "interpolated": False,
        }

    if target <= timed[0]["source_time"]:
        return {
            **timed[0],
            "interpolated": False,
        }

    if target >= timed[-1]["source_time"]:
        return {
            **timed[-1],
            "interpolated": False,
        }

    lo = 0
    hi = len(timed) - 1

    while lo + 1 < hi:
        mid = (lo + hi) // 2

        if timed[mid]["source_time"] <= target:
            lo = mid
        else:
            hi = mid

    a = timed[lo]
    b = timed[hi]

    span = b["source_time"] - a["source_time"]
    alpha = 0.0 if span <= 0 else (target - a["source_time"]) / span

    quat = _slerp(a["quat"], b["quat"], alpha)

    return {
        "source_time": target,
        "frame_index": a.get("frame_index"),
        "next_frame_index": b.get("frame_index"),
        "alpha": float(alpha),
        "quat": quat,
        "source": a.get("source"),
        "interpolated": True,
    }


def orientation_at_source_time(
    osv_path,
    source_time,
    *,
    source="highrate",
    imu_offset_ms=0.0,
):
    samples = extract_orientation_samples(osv_path, source=source)

    return orientation_from_samples(
        samples,
        float(source_time) + float(imu_offset_ms) / 1000.0,
    )
