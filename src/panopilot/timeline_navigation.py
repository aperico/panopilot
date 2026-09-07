"""Shared timeline viewport/navigation model for desktop editing surfaces.

The model is deliberately GUI-framework agnostic. Reframe/Trim and Project
Arrange timelines all use the same semantics:

- a visible time window over a fixed total duration;
- wheel-style zoom around an anchor time;
- horizontal pan;
- fit-to-duration;
- ensure-visible behavior used by playback autoscroll.

Qt widgets translate pixels/scrollbars into these operations but do not own the
navigation semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass
class TimelineViewport:
    duration: float
    visible_start: float = 0.0
    visible_duration: float | None = None
    min_visible_duration: float = 0.25
    zoom_base: float = 1.25

    def __post_init__(self):
        self.duration = max(0.0, float(self.duration))
        self.min_visible_duration = max(0.01, float(self.min_visible_duration))
        self.zoom_base = max(1.01, float(self.zoom_base))
        if self.visible_duration is None:
            self.visible_duration = self.duration
        self.visible_duration = self._clamp_visible_duration(self.visible_duration)
        self.visible_start = self._clamp_start(self.visible_start)

    def _clamp_visible_duration(self, value):
        if self.duration <= 0.0:
            return 0.0
        return max(
            min(self.min_visible_duration, self.duration),
            min(float(value), self.duration),
        )

    def _clamp_start(self, value):
        if self.duration <= 0.0:
            return 0.0
        maximum = max(0.0, self.duration - self.visible_duration)
        return max(0.0, min(float(value), maximum))

    @property
    def visible_end(self):
        return min(self.duration, self.visible_start + self.visible_duration)

    @property
    def is_fitted(self):
        return self.duration <= 0.0 or self.visible_duration >= self.duration - 1e-9

    @property
    def zoom_ratio(self):
        if self.duration <= 0.0 or self.visible_duration <= 0.0:
            return 1.0
        return self.duration / self.visible_duration

    def fit(self):
        self.visible_start = 0.0
        self.visible_duration = self.duration
        return self.snapshot()

    def set_window(self, start, duration):
        self.visible_duration = self._clamp_visible_duration(duration)
        self.visible_start = self._clamp_start(start)
        return self.snapshot()

    def zoom_steps(self, steps, *, anchor_time=None):
        """Zoom using conventional positive=in semantics.

        ``steps`` is normally a mouse-wheel notch count. Positive values zoom
        in, negative values zoom out. The time under the pointer/playhead is
        kept at the same relative location in the visible window whenever
        possible.
        """
        if self.duration <= 0.0:
            return self.snapshot()

        steps = float(steps)
        if abs(steps) <= 1e-12:
            return self.snapshot()

        old_duration = self.visible_duration
        old_start = self.visible_start
        anchor = (
            old_start + old_duration / 2.0
            if anchor_time is None
            else max(0.0, min(float(anchor_time), self.duration))
        )
        if old_duration <= 0.0:
            anchor_fraction = 0.5
        else:
            anchor_fraction = max(
                0.0,
                min(1.0, (anchor - old_start) / old_duration),
            )

        factor = self.zoom_base ** steps
        new_duration = self._clamp_visible_duration(old_duration / factor)
        self.visible_duration = new_duration
        self.visible_start = self._clamp_start(
            anchor - anchor_fraction * new_duration
        )
        return self.snapshot()

    def pan_seconds(self, delta_seconds):
        self.visible_start = self._clamp_start(
            self.visible_start + float(delta_seconds)
        )
        return self.snapshot()

    def pan_fraction(self, fraction):
        return self.pan_seconds(float(fraction) * self.visible_duration)

    def ensure_visible(self, source_time, *, margin_ratio=0.12):
        """Pan only when needed so ``source_time`` stays comfortably visible."""
        if self.is_fitted or self.duration <= 0.0:
            return False

        value = max(0.0, min(float(source_time), self.duration))
        margin = max(0.0, min(0.45, float(margin_ratio))) * self.visible_duration
        left_limit = self.visible_start + margin
        right_limit = self.visible_end - margin
        old_start = self.visible_start

        if value < left_limit:
            self.visible_start = self._clamp_start(value - margin)
        elif value > right_limit:
            self.visible_start = self._clamp_start(
                value - (self.visible_duration - margin)
            )

        return abs(self.visible_start - old_start) > 1e-9

    def time_for_fraction(self, fraction):
        fraction = max(0.0, min(1.0, float(fraction)))
        return self.visible_start + fraction * self.visible_duration

    def fraction_for_time(self, source_time):
        if self.visible_duration <= 0.0:
            return 0.0
        return max(
            0.0,
            min(
                1.0,
                (float(source_time) - self.visible_start) / self.visible_duration,
            ),
        )

    def scrollbar_state_ms(self):
        """Return absolute-ms values suitable for a horizontal QScrollBar."""
        duration_ms = max(0, int(round(self.duration * 1000.0)))
        page_ms = max(1, int(round(self.visible_duration * 1000.0)))
        maximum = max(0, duration_ms - page_ms)
        value = max(0, min(maximum, int(round(self.visible_start * 1000.0))))
        return {
            "minimum": 0,
            "maximum": maximum,
            "page_step": page_ms,
            "value": value,
        }

    def snapshot(self):
        return {
            "duration": float(self.duration),
            "visible_start": float(self.visible_start),
            "visible_end": float(self.visible_end),
            "visible_duration": float(self.visible_duration),
            "zoom_ratio": float(self.zoom_ratio),
            "fitted": bool(self.is_fitted),
        }


def wheel_steps(delta_y):
    """Normalize common Qt-style wheel deltas to logical notches."""
    value = float(delta_y)
    return value / 120.0 if value else 0.0


def proportional_clip_widths(durations, *, total_pixel_width, minimum_width=72):
    """Return duration-proportional clip widths while preserving usability.

    When the requested minimums exceed the available width, the result is
    allowed to exceed ``total_pixel_width``; a scroll container is expected to
    expose the overflow. This is preferable to making short clips impossible to
    select or drag.
    """
    values = [max(0.0, float(value)) for value in durations]
    count = len(values)
    if not count:
        return []
    minimum_width = max(24, int(minimum_width))
    total_pixel_width = max(count * minimum_width, int(total_pixel_width))
    total_duration = sum(values)
    if total_duration <= 1e-12:
        return [minimum_width] * count

    raw = [max(minimum_width, int(round(total_pixel_width * value / total_duration))) for value in values]
    return raw
