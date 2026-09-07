"""
High-rate adaptive gyro stabilization for PanoPilot.

This module is a clean-room implementation informed by public video-
stabilization literature and the general principle used by professional gyro
stabilizers: smooth the full orientation trajectory at native IMU rate, adapt
smoothing to angular velocity, and only then sample the desired trajectory at
video exposure times.

It intentionally does not copy or translate third-party implementation code.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


def _normalize_quaternions(quaternions):
    q = np.asarray(quaternions, dtype=np.float64).copy()
    if q.ndim != 2 or q.shape[1] != 4:
        raise ValueError("Expected an Nx4 quaternion sequence")
    if len(q) == 0:
        return q
    norms = np.linalg.norm(q, axis=1, keepdims=True)
    norms = np.where(norms < 1e-12, 1.0, norms)
    q /= norms
    for i in range(1, len(q)):
        if float(np.dot(q[i - 1], q[i])) < 0.0:
            q[i] *= -1.0
    return q


def _slerp(a, b, alpha):
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    a = a / max(float(np.linalg.norm(a)), 1e-12)
    b = b / max(float(np.linalg.norm(b)), 1e-12)
    dot = float(np.dot(a, b))
    if dot < 0.0:
        b = -b
        dot = -dot
    dot = max(-1.0, min(1.0, dot))
    alpha = max(0.0, min(1.0, float(alpha)))
    if dot > 0.9995:
        out = a + alpha * (b - a)
        return out / max(float(np.linalg.norm(out)), 1e-12)
    theta = math.acos(dot)
    sin_theta = math.sin(theta)
    if abs(sin_theta) < 1e-12:
        return a.copy()
    out = (
        math.sin((1.0 - alpha) * theta) / sin_theta * a
        + math.sin(alpha * theta) / sin_theta * b
    )
    return out / max(float(np.linalg.norm(out)), 1e-12)


def _quat_angle_rad(a, b):
    dot = abs(float(np.dot(a, b)))
    dot = max(-1.0, min(1.0, dot))
    return 2.0 * math.acos(dot)


def _zero_phase_scalar_lowpass(values, times, time_constant_s):
    values = np.asarray(values, dtype=np.float64)
    times = np.asarray(times, dtype=np.float64)
    if len(values) <= 1 or time_constant_s <= 1e-9:
        return values.copy()
    forward = values.copy()
    for i in range(1, len(values)):
        dt = max(1e-6, float(times[i] - times[i - 1]))
        alpha = 1.0 - math.exp(-dt / float(time_constant_s))
        forward[i] = forward[i - 1] + alpha * (values[i] - forward[i - 1])
    out = forward.copy()
    for i in range(len(values) - 2, -1, -1):
        dt = max(1e-6, float(times[i + 1] - times[i]))
        alpha = 1.0 - math.exp(-dt / float(time_constant_s))
        out[i] = out[i + 1] + alpha * (forward[i] - out[i + 1])
    return out


def _adaptive_quaternion_pass(quaternions, times, time_constants):
    q = _normalize_quaternions(quaternions)
    times = np.asarray(times, dtype=np.float64)
    tau = np.asarray(time_constants, dtype=np.float64)
    if len(q) <= 1:
        return q

    forward = np.empty_like(q)
    forward[0] = q[0]
    for i in range(1, len(q)):
        dt = max(1e-6, float(times[i] - times[i - 1]))
        alpha = 1.0 - math.exp(-dt / max(float(tau[i]), 1e-6))
        forward[i] = _slerp(forward[i - 1], q[i], alpha)

    # Reverse pass removes most phase bias and strengthens rejection of short
    # oscillations without turning this into a causal/lagging real-time filter.
    out = np.empty_like(q)
    out[-1] = forward[-1]
    for i in range(len(q) - 2, -1, -1):
        dt = max(1e-6, float(times[i + 1] - times[i]))
        alpha = 1.0 - math.exp(-dt / max(float(tau[i]), 1e-6))
        out[i] = _slerp(out[i + 1], forward[i], alpha)
    return _normalize_quaternions(out)


def adaptive_profile(amount):
    """Map the User's 0..1 amount to trajectory-filter parameters."""
    a = max(0.0, min(1.0, float(amount)))
    # At high amount, small/medium motions are treated almost like a virtual
    # gimbal, while genuinely fast intentional turns still get a much shorter
    # time constant and can be followed.
    low_velocity_tau_s = 0.20 + 2.80 * (a ** 1.35)
    high_velocity_tau_s = 0.035 + 0.265 * a
    velocity_threshold_deg_s = 650.0 - 500.0 * a
    velocity_filter_tau_s = 0.075 + 0.075 * a
    correction_gain = 1.0 - (1.0 - a) ** 3
    passes = 2 if a >= 0.20 else 1
    return {
        "low_velocity_tau_s": float(low_velocity_tau_s),
        "high_velocity_tau_s": float(high_velocity_tau_s),
        "velocity_threshold_deg_s": float(velocity_threshold_deg_s),
        "velocity_filter_tau_s": float(velocity_filter_tau_s),
        "correction_gain": float(correction_gain),
        "passes": int(passes),
    }


@dataclass(frozen=True)
class StabilizationTrajectory:
    times: np.ndarray
    raw_quaternions: np.ndarray
    stable_quaternions: np.ndarray
    diagnostics: dict


def build_adaptive_trajectory(samples, amount):
    timed = [
        sample for sample in samples
        if sample.get("source_time") is not None and sample.get("quat") is not None
    ]
    if not timed:
        raise RuntimeError("Timed orientation samples are required for stabilization")
    timed = sorted(timed, key=lambda sample: float(sample["source_time"]))
    times = np.asarray([float(s["source_time"]) for s in timed], dtype=np.float64)
    raw = _normalize_quaternions([s["quat"] for s in timed])

    # Deduplicate non-increasing timestamps defensively.
    if len(times) > 1:
        keep = np.ones(len(times), dtype=bool)
        keep[1:] = np.diff(times) > 1e-9
        times = times[keep]
        raw = raw[keep]
    if len(times) == 0:
        raise RuntimeError("No usable timed orientation samples remain")

    a = max(0.0, min(1.0, float(amount)))
    profile = adaptive_profile(a)

    velocity = np.zeros(len(raw), dtype=np.float64)
    if len(raw) > 1:
        for i in range(1, len(raw)):
            dt = max(1e-6, float(times[i] - times[i - 1]))
            velocity[i] = math.degrees(_quat_angle_rad(raw[i - 1], raw[i])) / dt
        velocity[0] = velocity[1]

    filtered_velocity = _zero_phase_scalar_lowpass(
        velocity, times, profile["velocity_filter_tau_s"]
    )

    if a <= 1e-9:
        stable = raw.copy()
        time_constants = np.zeros(len(raw), dtype=np.float64)
    else:
        ratio = np.clip(
            filtered_velocity / max(profile["velocity_threshold_deg_s"], 1e-6),
            0.0,
            1.0,
        )
        # Smoothstep-shaped interpolation: very low velocity keeps maximum
        # damping; only sustained motion relaxes the trajectory filter.
        blend = ratio * ratio * (3.0 - 2.0 * ratio)
        time_constants = (
            profile["low_velocity_tau_s"] * (1.0 - blend)
            + profile["high_velocity_tau_s"] * blend
        )
        stable = raw.copy()
        for _ in range(profile["passes"]):
            stable = _adaptive_quaternion_pass(stable, times, time_constants)

    stable_velocity = np.zeros(len(stable), dtype=np.float64)
    correction_angle = np.zeros(len(stable), dtype=np.float64)
    if len(stable) > 1:
        for i in range(1, len(stable)):
            dt = max(1e-6, float(times[i] - times[i - 1]))
            stable_velocity[i] = math.degrees(
                _quat_angle_rad(stable[i - 1], stable[i])
            ) / dt
        stable_velocity[0] = stable_velocity[1]
    for i in range(len(stable)):
        correction_angle[i] = math.degrees(_quat_angle_rad(raw[i], stable[i]))

    dt = np.diff(times)
    valid_dt = dt[dt > 1e-9]
    sample_rate_hz = (
        float(1.0 / np.median(valid_dt)) if len(valid_dt) else None
    )

    def percentile(values, q):
        return float(np.percentile(values, q)) if len(values) else 0.0

    diagnostics = {
        "algorithm": "adaptive-highrate-v1",
        "amount": float(a),
        "sample_count": int(len(times)),
        "sample_rate_hz": sample_rate_hz,
        **profile,
        "raw_velocity_mean_deg_s": float(np.mean(velocity)) if len(velocity) else 0.0,
        "raw_velocity_p95_deg_s": percentile(velocity, 95),
        "raw_velocity_max_deg_s": float(np.max(velocity)) if len(velocity) else 0.0,
        "stable_velocity_mean_deg_s": float(np.mean(stable_velocity)) if len(stable_velocity) else 0.0,
        "stable_velocity_p95_deg_s": percentile(stable_velocity, 95),
        "stable_velocity_max_deg_s": float(np.max(stable_velocity)) if len(stable_velocity) else 0.0,
        "correction_angle_mean_deg": float(np.mean(correction_angle)) if len(correction_angle) else 0.0,
        "correction_angle_p95_deg": percentile(correction_angle, 95),
        "correction_angle_max_deg": float(np.max(correction_angle)) if len(correction_angle) else 0.0,
        "time_constant_min_s": float(np.min(time_constants)) if len(time_constants) else 0.0,
        "time_constant_max_s": float(np.max(time_constants)) if len(time_constants) else 0.0,
    }
    return StabilizationTrajectory(times, raw, stable, diagnostics)


def _sample_quaternion(times, quaternions, target):
    target = float(target)
    if target <= times[0]:
        return quaternions[0].copy()
    if target >= times[-1]:
        return quaternions[-1].copy()
    hi = int(np.searchsorted(times, target, side="right"))
    lo = hi - 1
    span = float(times[hi] - times[lo])
    alpha = 0.0 if span <= 0.0 else (target - float(times[lo])) / span
    return _slerp(quaternions[lo], quaternions[hi], alpha)


def sample_trajectory(trajectory, exposure_times, *, imu_offset_ms=0.0):
    targets = np.asarray(exposure_times, dtype=np.float64) + float(imu_offset_ms) / 1000.0
    raw = np.asarray([
        _sample_quaternion(trajectory.times, trajectory.raw_quaternions, t)
        for t in targets
    ], dtype=np.float64)
    stable = np.asarray([
        _sample_quaternion(trajectory.times, trajectory.stable_quaternions, t)
        for t in targets
    ], dtype=np.float64)
    return raw, stable
