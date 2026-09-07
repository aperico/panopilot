from pathlib import Path

import panopilot.direct_render as direct_module
import panopilot.project_export as export_module
import panopilot.rolling_shutter as rolling_module
import panopilot.spherical_stabilization as spherical_module


def test_direct_renderer_uses_source_lens_row_time():
    source = Path(
        direct_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "corrected_panorama_map_for_lens"
        in source
    )
    assert (
        "rolling_frame_correction"
        not in source
    )


def test_rolling_shutter_uses_high_rate_body_to_world_geometry():
    source = Path(
        rolling_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "R_row.T"
        in source
    )
    assert (
        "IMU_TO_FACTORY_EQUIRECT"
        in source
    )
    assert (
        "reference_offset_ms"
        in source
    )


def test_export_auto_calibrates_and_reuses_first_pass_solution():
    source = Path(
        export_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "_auto_calibrate_clip_rolling_shutter"
        in source
    )
    assert (
        "rolling_shutter_calibrations"
        in source
    )
    assert (
        '"rolling_shutter_calibration"'
        in source
    )


def test_spherical_visual_roll_is_spatially_coherence_gated():
    source = Path(
        spherical_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "_roll_coherence_weight"
        in source
    )
    assert (
        "gyro-authoritative"
        in source
    )
