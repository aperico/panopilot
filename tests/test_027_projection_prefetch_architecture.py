from pathlib import Path

import panopilot.project_export as export_module
import panopilot.projection_prefetch as prefetch_module


def test_prefetch_uses_one_worker_and_one_pending_map():
    source = Path(
        prefetch_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert "max_workers=1" in source
    assert "already has a pending map" in source


def test_export_profiles_serial_wait_separately():
    source = Path(
        export_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert '"projection_map_wait"' in source
    assert '"map_generation_worker"' in source
    assert "ProjectionMapPrefetcher" in source
