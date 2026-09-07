\
"""Experimental direct dual-lens final renderer for PanoPilot."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
import math
import time

import cv2
import numpy as np

from .rolling_shutter import (
    corrected_panorama_map_for_lens,
    panorama_map_to_directions,
)


@dataclass(frozen=True)
class DirectLensMaps:
    lens0_x: np.ndarray
    lens0_y: np.ndarray
    lens1_x: np.ndarray
    lens1_y: np.ndarray
    weight0: np.ndarray
    weight1: np.ndarray
    uncovered: np.ndarray
    worker_seconds: float


class DirectLensRenderer:
    """
    Compose static factory panorama maps with a dynamic Camera/horizon map.

    The accepted panorama path first remaps both lenses to a full panorama,
    blends there, and then remaps the panorama to delivery resolution. This
    experimental path samples the static factory map fields at delivery pixels,
    then remaps each original lens directly to the delivery frame and blends
    there.

    Weighted coordinate fields prevent factory invalid coordinates (-1) from
    bleeding into valid output-map coordinates during bilinear composition.
    """

    def __init__(self, factory_mapper):
        self.mapper = factory_mapper
        diagnostics = getattr(
            factory_mapper,
            "diagnostics",
            None,
        )
        self._w0 = np.asarray(factory_mapper.w0, dtype=np.float32)
        self._w1 = np.asarray(factory_mapper.w1, dtype=np.float32)

        self.panorama_height = int(
            getattr(
                factory_mapper,
                "out_h",
                self._w0.shape[0],
            )
        )
        self.panorama_width = int(
            getattr(
                factory_mapper,
                "out_w",
                self._w0.shape[1],
            )
        )

        if diagnostics is not None and hasattr(
            diagnostics,
            "source_height",
        ):
            self.source_height = int(
                diagnostics.source_height
            )
        else:
            # Synthetic/unit-test mappers predate source diagnostics. Infer a
            # conservative source height from the valid factory-map Y domain.
            valid_y = np.concatenate(
                (
                    np.asarray(
                        factory_mapper.map0_y,
                        dtype=np.float32,
                    ).ravel(),
                    np.asarray(
                        factory_mapper.map1_y,
                        dtype=np.float32,
                    ).ravel(),
                )
            )
            valid_y = valid_y[
                np.isfinite(valid_y)
                & (
                    valid_y >= 0.0
                )
            ]
            self.source_height = max(
                1,
                int(
                    math.ceil(
                        float(
                            np.max(valid_y)
                        )
                        + 1.0
                    )
                )
                if len(valid_y)
                else self.panorama_height,
            )
        self._m0xw = np.where(
            self._w0 > 0.0,
            np.asarray(factory_mapper.map0_x, dtype=np.float32) * self._w0,
            0.0,
        ).astype(np.float32)
        self._m0yw = np.where(
            self._w0 > 0.0,
            np.asarray(factory_mapper.map0_y, dtype=np.float32) * self._w0,
            0.0,
        ).astype(np.float32)
        self._m1xw = np.where(
            self._w1 > 0.0,
            np.asarray(factory_mapper.map1_x, dtype=np.float32) * self._w1,
            0.0,
        ).astype(np.float32)
        self._m1yw = np.where(
            self._w1 > 0.0,
            np.asarray(factory_mapper.map1_y, dtype=np.float32) * self._w1,
            0.0,
        ).astype(np.float32)

    @staticmethod
    def _sample(field, map_x, map_y):
        # RectilinearProjector clamps Y. X is periodic, so BORDER_WRAP only
        # matters at the equirectangular horizontal seam.
        return cv2.remap(
            field,
            map_x,
            map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_WRAP,
        )

    @staticmethod
    def _recover(weighted_coordinate, weight, epsilon=1e-6):
        out = np.full(weight.shape, -1.0, dtype=np.float32)
        valid = weight > np.float32(epsilon)
        np.divide(weighted_coordinate, weight, out=out, where=valid)
        return out

    def _compose_lens(
        self,
        panorama_map_x,
        panorama_map_y,
        *,
        weight,
        map_x_weighted,
        map_y_weighted,
    ):
        sampled_weight = self._sample(
            weight,
            panorama_map_x,
            panorama_map_y,
        )
        map_x = self._recover(
            self._sample(
                map_x_weighted,
                panorama_map_x,
                panorama_map_y,
            ),
            sampled_weight,
        )
        map_y = self._recover(
            self._sample(
                map_y_weighted,
                panorama_map_x,
                panorama_map_y,
            ),
            sampled_weight,
        )
        return (
            sampled_weight,
            map_x,
            map_y,
        )

    def compose_maps(
        self,
        panorama_map_x,
        panorama_map_y,
        *,
        rolling_shutter=None,
    ):
        started = time.perf_counter()

        w0, m0x, m0y = self._compose_lens(
            panorama_map_x,
            panorama_map_y,
            weight=self._w0,
            map_x_weighted=self._m0xw,
            map_y_weighted=self._m0yw,
        )
        w1, m1x, m1y = self._compose_lens(
            panorama_map_x,
            panorama_map_y,
            weight=self._w1,
            map_x_weighted=self._m1xw,
            map_y_weighted=self._m1yw,
        )

        if (
            rolling_shutter is not None
            and rolling_shutter.enabled
        ):
            base_directions = (
                panorama_map_to_directions(
                    panorama_map_x,
                    panorama_map_y,
                    self.panorama_width,
                    self.panorama_height,
                )
            )

            # Correct each lens independently because the row exposure time is
            # defined in that source sensor's coordinates. Re-evaluate the row
            # after the first correction because the corrected ray can move to
            # a slightly different source Y coordinate.
            iterations = max(
                1,
                int(
                    rolling_shutter.iterations
                ),
            )

            for _ in range(
                iterations
            ):
                p0x, p0y = (
                    corrected_panorama_map_for_lens(
                        panorama_map_x,
                        panorama_map_y,
                        m0y,
                        source_height=(
                            self.source_height
                        ),
                        panorama_width=(
                            self.panorama_width
                        ),
                        panorama_height=(
                            self.panorama_height
                        ),
                        correction=(
                            rolling_shutter
                        ),
                        base_directions=(
                            base_directions
                        ),
                    )
                )
                w0, m0x, m0y = (
                    self._compose_lens(
                        p0x,
                        p0y,
                        weight=self._w0,
                        map_x_weighted=(
                            self._m0xw
                        ),
                        map_y_weighted=(
                            self._m0yw
                        ),
                    )
                )

                p1x, p1y = (
                    corrected_panorama_map_for_lens(
                        panorama_map_x,
                        panorama_map_y,
                        m1y,
                        source_height=(
                            self.source_height
                        ),
                        panorama_width=(
                            self.panorama_width
                        ),
                        panorama_height=(
                            self.panorama_height
                        ),
                        correction=(
                            rolling_shutter
                        ),
                        base_directions=(
                            base_directions
                        ),
                    )
                )
                w1, m1x, m1y = (
                    self._compose_lens(
                        p1x,
                        p1y,
                        weight=self._w1,
                        map_x_weighted=(
                            self._m1xw
                        ),
                        map_y_weighted=(
                            self._m1yw
                        ),
                    )
                )

        total = w0 + w1
        uncovered = (
            total
            <= np.float32(
                1e-6
            )
        )
        safe = np.where(
            uncovered,
            np.float32(
                1.0
            ),
            total,
        ).astype(
            np.float32
        )
        w0 = (
            w0
            / safe
        ).astype(
            np.float32
        )
        w1 = (
            w1
            / safe
        ).astype(
            np.float32
        )

        return DirectLensMaps(
            lens0_x=m0x,
            lens0_y=m0y,
            lens1_x=m1x,
            lens1_y=m1y,
            weight0=w0,
            weight1=w1,
            uncovered=uncovered,
            worker_seconds=(
                time.perf_counter()
                - started
            ),
        )

    def render(self, lens0, lens1, maps: DirectLensMaps):
        p0 = cv2.remap(
            lens0, maps.lens0_x, maps.lens0_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
        )
        p1 = cv2.remap(
            lens1, maps.lens1_x, maps.lens1_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
        )
        out = cv2.blendLinear(p0, p1, maps.weight0, maps.weight1)
        out[maps.uncovered] = 0
        return out


@dataclass(frozen=True)
class DirectMapPrefetchResult:
    maps: DirectLensMaps
    projection_seconds: float
    composition_seconds: float


def _generate_direct_maps(projector, renderer, camera, content_rotation, rolling_shutter=None):
    started = time.perf_counter()
    map_x, map_y = projector.map(
        camera,
        content_rotation=content_rotation,
    )
    projection_seconds = time.perf_counter() - started
    maps = renderer.compose_maps(
        map_x,
        map_y,
        rolling_shutter=(
            rolling_shutter
        ),
    )
    return DirectMapPrefetchResult(
        maps=maps,
        projection_seconds=projection_seconds,
        composition_seconds=maps.worker_seconds,
    )


class DirectMapPrefetcher:
    """One worker and at most one outstanding direct-map set."""

    def __init__(self, projector, renderer, *, enabled=True):
        self.projector = projector
        self.renderer = renderer
        self.enabled = bool(enabled)
        self._executor = (
            ThreadPoolExecutor(max_workers=1, thread_name_prefix='panopilot-direct-map')
            if self.enabled else None
        )
        self._pending = None

    def submit(self, camera, content_rotation, rolling_shutter=None):
        if self._pending is not None:
            raise RuntimeError('direct-map prefetch already has a pending frame')
        args=(self.projector,self.renderer,camera,content_rotation,rolling_shutter)
        if self._executor is None:
            self._pending=args
        else:
            self._pending=self._executor.submit(_generate_direct_maps,*args)

    def result(self):
        if self._pending is None:
            raise RuntimeError('direct-map prefetch has no pending frame')
        pending=self._pending; self._pending=None
        if isinstance(pending, Future):
            return pending.result()
        return _generate_direct_maps(*pending)

    def close(self):
        if self._executor is not None:
            self._executor.shutdown(wait=True,cancel_futures=False)
            self._executor=None

    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb):
        self.close(); return False
