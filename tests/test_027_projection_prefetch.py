import numpy as np
import pytest

from panopilot.projection_prefetch import (
    ProjectionMapPrefetcher,
)
from panopilot.virtual_camera import (
    RectilinearProjector,
    VirtualCamera,
)


def test_prefetched_map_is_identical_to_sequential_map():
    projector = RectilinearProjector(
        720,
        360,
        320,
        180,
    )
    camera = VirtualCamera(
        22.0,
        -7.0,
        81.0,
    )
    rotation = np.eye(
        3,
        dtype=np.float64,
    )

    expected_x, expected_y = projector.map(
        camera,
        content_rotation=rotation,
    )

    with ProjectionMapPrefetcher(
        projector,
        enabled=True,
    ) as prefetch:
        prefetch.submit(
            camera,
            rotation,
        )
        result = prefetch.result()

    assert np.array_equal(
        result.map_x,
        expected_x,
    )
    assert np.array_equal(
        result.map_y,
        expected_y,
    )


def test_disabled_prefetch_uses_same_api_and_geometry():
    projector = RectilinearProjector(
        720,
        360,
        160,
        90,
    )
    camera = VirtualCamera(
        5.0,
        2.0,
        90.0,
    )

    expected_x, expected_y = projector.map(
        camera,
    )

    with ProjectionMapPrefetcher(
        projector,
        enabled=False,
    ) as prefetch:
        prefetch.submit(
            camera,
            None,
        )
        result = prefetch.result()

    assert np.array_equal(
        result.map_x,
        expected_x,
    )
    assert np.array_equal(
        result.map_y,
        expected_y,
    )


def test_prefetch_is_bounded_to_one_pending_map():
    projector = RectilinearProjector(
        360,
        180,
        80,
        45,
    )

    with ProjectionMapPrefetcher(
        projector,
        enabled=True,
    ) as prefetch:
        prefetch.submit(
            VirtualCamera(),
            None,
        )

        with pytest.raises(
            RuntimeError,
            match="already has a pending map",
        ):
            prefetch.submit(
                VirtualCamera(),
                None,
            )

        prefetch.result()
