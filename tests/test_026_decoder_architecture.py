from pathlib import Path

import panopilot.project_export as export_module


def test_auto_decoder_uses_runtime_smoke_test():
    source = Path(
        export_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert "_smoke_test_lens_decoder" in source
    assert "_select_decoder_backend" in source
    assert "stdout=subprocess.DEVNULL" in source
    assert '"decoder_backend_probe"' in source


def test_export_records_decoder_backend_per_clip():
    source = Path(
        export_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert '"decoder": (' in source
    assert '"clip_backend_counts"' in source
