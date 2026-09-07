from pathlib import Path

import panopilot.cli as cli_module
import panopilot.export_ui as export_ui_module
import panopilot.project_editor as editor_module
import panopilot.project_export as export_module


def test_project_editor_confirms_export_summary_before_starting():
    source = Path(
        editor_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert "build_export_summary" in source
    assert "Ready to export?" in source
    assert "File size depends on video content" in source


def test_gui_export_uses_dedicated_progress_and_completion_dialogs():
    source = Path(
        cli_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert "run_export_with_progress_dialog" in source
    assert "show_export_completion_dialog" in source
    assert "show_export_error_dialog" in source


def test_export_progress_ui_exposes_open_folder_action():
    source = Path(
        export_ui_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert '"Open Folder"' in source
    assert "QDesktopServices.openUrl" in source
    assert "Remaining" in source


def test_exporter_reports_final_file_size_and_render_pass_progress():
    source = Path(
        export_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert '"output_file_size_bytes"' in source
    assert "render_pass_index" in source
    assert "rolling-shutter-calibration-progress" in source
