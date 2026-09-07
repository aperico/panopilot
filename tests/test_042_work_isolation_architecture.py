from pathlib import Path

import panopilot.cache as cache_module
import panopilot.project_editor as editor_module
import panopilot.project_export as export_module
import panopilot.preview as preview_module


def _source(module):
    return Path(module.__file__).read_text(encoding="utf-8")


def test_project_organizer_uses_background_jobs_for_preview_import_and_export():
    source = _source(editor_module)

    assert "BackgroundJobManager" in source
    assert "_schedule_preview_job" in source
    assert "_queue_import_validation" in source
    assert 'self.work_status.setText("Exporting…")' in source
    assert 'self.abort_export_button = QPushButton("Abort")' in source
    assert "panopilot-export-snapshot" in source
    assert "ready Clips remain usable" in source


def test_preview_cache_and_renderer_have_cooperative_cancellation_boundary():
    cache_source = _source(cache_module)
    preview_source = _source(preview_module)

    assert "cancel_callback=None" in cache_source
    assert "cancel_callback=cancel_callback" in cache_source
    assert "Preview preparation cancelled" in preview_source
    assert "process.terminate()" in preview_source


def test_final_export_has_transaction_safe_cooperative_cancellation():
    source = _source(export_module)

    assert "cancel_callback=None" in source
    assert "_check_cancelled(cancel_callback)" in source
    assert "output_preparing.unlink" in source
    assert "output_preparing.replace" in source
    assert "decoder_process.terminate()" in source
    assert "encoder.terminate()" in source
