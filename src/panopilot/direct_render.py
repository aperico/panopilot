\
"""Experimental direct dual-lens final renderer for PanoPilot."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
import time

import cv2
import numpy as np


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
        self._w0 = np.asarray(factory_mapper.w0, dtype=np.float32)
        self._w1 = np.asarray(factory_mapper.w1, dtype=np.float32)

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

    def compose_maps(self, panorama_map_x, panorama_map_y):
        started = time.perf_counter()

        w0 = self._sample(self._w0, panorama_map_x, panorama_map_y)
        w1 = self._sample(self._w1, panorama_map_x, panorama_map_y)

        m0x = self._recover(
            self._sample(self._m0xw, panorama_map_x, panorama_map_y), w0
        )
        m0y = self._recover(
            self._sample(self._m0yw, panorama_map_x, panorama_map_y), w0
        )
        m1x = self._recover(
            self._sample(self._m1xw, panorama_map_x, panorama_map_y), w1
        )
        m1y = self._recover(
            self._sample(self._m1yw, panorama_map_x, panorama_map_y), w1
        )

        total = w0 + w1
        uncovered = total <= np.float32(1e-6)
        safe = np.where(uncovered, np.float32(1.0), total).astype(np.float32)
        w0 = (w0 / safe).astype(np.float32)
        w1 = (w1 / safe).astype(np.float32)

        return DirectLensMaps(
            lens0_x=m0x,
            lens0_y=m0y,
            lens1_x=m1x,
            lens1_y=m1y,
            weight0=w0,
            weight1=w1,
            uncovered=uncovered,
            worker_seconds=time.perf_counter()-started,
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


def _generate_direct_maps(projector, renderer, camera, content_rotation):
    started = time.perf_counter()
    map_x, map_y = projector.map(
        camera,
        content_rotation=content_rotation,
    )
    projection_seconds = time.perf_counter() - started
    maps = renderer.compose_maps(map_x, map_y)
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

    def submit(self, camera, content_rotation):
        if self._pending is not None:
            raise RuntimeError('direct-map prefetch already has a pending frame')
        args=(self.projector,self.renderer,camera,content_rotation)
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
