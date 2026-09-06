"""Bounded one-frame-ahead projection-map generation."""
from __future__ import annotations

from concurrent.futures import (
    Future,
    ThreadPoolExecutor,
)
from dataclasses import dataclass
import time


@dataclass(frozen=True)
class ProjectionMapResult:
    map_x: object
    map_y: object
    worker_seconds: float


def _generate_projection_map(
    projector,
    camera,
    content_rotation,
):
    started = time.perf_counter()

    map_x, map_y = projector.map(
        camera,
        content_rotation=(
            content_rotation
        ),
    )

    return ProjectionMapResult(
        map_x=map_x,
        map_y=map_y,
        worker_seconds=(
            time.perf_counter()
            - started
        ),
    )


class ProjectionMapPrefetcher:
    """
    One worker and at most one outstanding map.

    Enabled mode starts map generation immediately on a worker thread.
    Disabled mode preserves the same API but performs the map synchronously
    when ``result()`` is requested, allowing a clean A/B benchmark.
    """

    def __init__(
        self,
        projector,
        *,
        enabled=True,
    ):
        self.projector = projector
        self.enabled = bool(
            enabled
        )
        self._executor = (
            ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix=(
                    "panopilot-map"
                ),
            )
            if self.enabled
            else None
        )
        self._pending = None

    @property
    def has_pending(self):
        return (
            self._pending
            is not None
        )

    def submit(
        self,
        camera,
        content_rotation,
    ):
        if self._pending is not None:
            raise RuntimeError(
                "projection prefetch already has a pending map"
            )

        if self._executor is None:
            self._pending = (
                camera,
                content_rotation,
            )
            return

        self._pending = (
            self._executor.submit(
                _generate_projection_map,
                self.projector,
                camera,
                content_rotation,
            )
        )

    def result(self):
        if self._pending is None:
            raise RuntimeError(
                "projection prefetch has no pending map"
            )

        pending = self._pending
        self._pending = None

        if isinstance(
            pending,
            Future,
        ):
            return pending.result()

        camera, content_rotation = (
            pending
        )
        return _generate_projection_map(
            self.projector,
            camera,
            content_rotation,
        )

    def close(self):
        if self._executor is not None:
            self._executor.shutdown(
                wait=True,
                cancel_futures=False,
            )
            self._executor = None

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        self.close()
        return False
