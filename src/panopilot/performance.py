"""Lightweight performance instrumentation for PanoPilot export."""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
import time


@dataclass(frozen=True)
class StageMetric:
    seconds: float
    calls: int

    def to_dict(self, *, total_seconds=None):
        result = {
            "seconds": float(self.seconds),
            "calls": int(self.calls),
            "mean_ms": (
                float(self.seconds)
                * 1000.0
                / max(1, int(self.calls))
            ),
        }

        if (
            total_seconds is not None
            and float(total_seconds) > 0.0
        ):
            result["share_percent"] = (
                100.0
                * float(self.seconds)
                / float(total_seconds)
            )

        return result


class StageProfiler:
    """
    Aggregate wall-clock time and call counts by named stage.

    The profiler is deliberately simple: ``time.perf_counter`` around semantic
    boundaries. It adds negligible complexity and is suitable for identifying
    the dominant final-export cost before choosing deeper optimization work.
    """

    def __init__(self):
        self._seconds = defaultdict(float)
        self._calls = defaultdict(int)

    @contextmanager
    def measure(self, name):
        name = str(name)
        started = time.perf_counter()

        try:
            yield
        finally:
            self._seconds[name] += (
                time.perf_counter()
                - started
            )
            self._calls[name] += 1

    def add(self, name, seconds, *, calls=1):
        name = str(name)
        self._seconds[name] += max(
            0.0,
            float(seconds),
        )
        self._calls[name] += max(
            0,
            int(calls),
        )

    def metric(self, name):
        return StageMetric(
            seconds=float(
                self._seconds.get(
                    str(name),
                    0.0,
                )
            ),
            calls=int(
                self._calls.get(
                    str(name),
                    0,
                )
            ),
        )

    def total_measured_seconds(self):
        return float(
            sum(
                self._seconds.values()
            )
        )

    def summary(
        self,
        *,
        total_seconds=None,
        include_zero=False,
    ):
        names = sorted(
            set(self._seconds)
            | set(self._calls)
        )

        result = {}

        for name in names:
            metric = self.metric(name)

            if (
                not include_zero
                and metric.seconds <= 0.0
                and metric.calls <= 0
            ):
                continue

            result[name] = metric.to_dict(
                total_seconds=total_seconds,
            )

        return result


def dominant_stage(
    stage_summary,
    *,
    exclude=None,
):
    exclude = set(
        exclude or ()
    )
    candidates = []

    for name, data in stage_summary.items():
        if name in exclude:
            continue

        seconds = float(
            data.get(
                "seconds",
                0.0,
            )
        )
        candidates.append(
            (
                seconds,
                name,
            )
        )

    if not candidates:
        return None

    seconds, name = max(
        candidates
    )

    return {
        "name": name,
        "seconds": float(seconds),
        "share_percent": float(
            stage_summary[
                name
            ].get(
                "share_percent",
                0.0,
            )
        ),
    }


def format_performance_summary(performance):
    """
    Compact terminal summary for user benchmarking.
    """
    if not performance:
        return "No performance data."

    lines = []

    elapsed = performance.get(
        "processing_seconds"
    )
    frames = performance.get(
        "frames"
    )
    fps = performance.get(
        "processing_fps"
    )

    if elapsed is not None:
        lines.append(
            f"Total export: {float(elapsed):.2f}s"
        )

    if (
        frames is not None
        and fps is not None
    ):
        lines.append(
            f"Render throughput: {int(frames)} frames @ {float(fps):.2f} fps"
        )

    dominant = performance.get(
        "dominant_video_stage"
    )

    if dominant:
        lines.append(
            "Dominant video stage: "
            f"{dominant['name']} "
            f"({float(dominant['share_percent']):.1f}%)"
        )

    stages = performance.get(
        "video_stage_timings",
        {}
    )

    ordered = sorted(
        stages.items(),
        key=lambda item: float(
            item[1].get(
                "seconds",
                0.0,
            )
        ),
        reverse=True,
    )

    for name, data in ordered:
        lines.append(
            f"  {name}: "
            f"{float(data.get('seconds', 0.0)):.2f}s "
            f"({float(data.get('share_percent', 0.0)):.1f}%)"
        )

    return "\n".join(
        lines
    )
