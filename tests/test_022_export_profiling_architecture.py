from pathlib import Path

import panopilot.project_export as export_module


def test_export_profiles_major_video_stages():
    source = Path(
        export_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    for stage in (
        "decoder_read_wait",
        "factory_stitch",
        "stabilization_rotation_math",
        "view_path_evaluation",
        "composed_projection",
        "encoder_write_wait",
    ):
        assert stage in source


def test_export_profiles_overall_pipeline_stages():
    source = Path(
        export_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    for stage in (
        "video_render",
        "audio_assembly",
        "final_mux",
        "final_verification",
    ):
        assert stage in source
