from panopilot.output_profile import export_quality_for_name, output_profile_for_aspect
from panopilot.project_export import _video_encoder_command


def test_high_quality_is_stronger_than_legacy_crf18_medium():
    high = export_quality_for_name("high")
    assert high.crf < 18
    assert high.preset == "slow"


def test_master_quality_is_available_for_transcode_safe_output():
    master = export_quality_for_name("master")
    assert master.crf == 10
    assert master.preset == "slow"


def test_4k_landscape_and_vertical_are_supported():
    assert (output_profile_for_aspect("16:9", "2160p").width, output_profile_for_aspect("16:9", "2160p").height) == (3840, 2160)
    assert (output_profile_for_aspect("9:16", "2160p").width, output_profile_for_aspect("9:16", "2160p").height) == (2160, 3840)


def test_final_encoder_uses_h264_high_profile_and_bt709_metadata():
    command = _video_encoder_command("out.mp4", width=1920, height=1080, fps=60, crf=16, preset="slow")
    joined = " ".join(command)
    assert "-profile:v high" in joined
    assert "-color_primaries bt709" in joined
    assert "-color_trc bt709" in joined
    assert "-colorspace bt709" in joined
    assert "-pix_fmt yuv420p" in joined
