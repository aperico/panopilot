from panopilot.output_profile import (
    DEFAULT_OUTPUT_QUALITY,
    DEFAULT_OUTPUT_RESOLUTION,
    export_quality_for_name,
    output_profile_for_aspect,
)
from panopilot.project import Project
from panopilot.session import ProjectSession


def test_720p_and_1080p_landscape_dimensions():
    p720 = output_profile_for_aspect(
        "16:9",
        "720p",
    )
    p1080 = output_profile_for_aspect(
        "16:9",
        "1080p",
    )

    assert (p720.width, p720.height) == (1280, 720)
    assert (p1080.width, p1080.height) == (1920, 1080)


def test_720p_and_1080p_portrait_dimensions():
    p720 = output_profile_for_aspect(
        "9:16",
        "720p",
    )
    p1080 = output_profile_for_aspect(
        "9:16",
        "1080p",
    )

    assert (p720.width, p720.height) == (720, 1280)
    assert (p1080.width, p1080.height) == (1080, 1920)


def test_quality_presets_order_fidelity_by_crf():
    standard = export_quality_for_name(
        "standard"
    )
    high = export_quality_for_name(
        "high"
    )
    very_high = export_quality_for_name(
        "very-high"
    )

    assert very_high.crf < high.crf < standard.crf
    assert high.crf == 18


def test_schema_v5_migrates_to_previous_1080_high_behavior():
    project = Project.from_dict(
        {
            "schema_version": 5,
            "output_frame": {
                "aspect": "16:9",
            },
            "camera_motion": {
                "easing": "smooth",
                "strength": 1.0,
            },
            "stabilization": {
                "amount": 0.5,
                "algorithm": "adaptive-highrate-v1",
            },
            "clips": [],
        }
    )

    assert project.output_resolution == DEFAULT_OUTPUT_RESOLUTION
    assert project.output_quality == DEFAULT_OUTPUT_QUALITY
    assert project.output_resolution == "1080p"
    assert project.output_quality == "high"


def test_output_options_round_trip_schema_v6():
    project = Project(
        output_resolution="720p",
        output_quality="very-high",
    )
    data = project.to_dict()

    assert data["schema_version"] == 8
    assert data["output_frame"]["resolution"] == "720p"
    assert data["output_frame"]["quality"] == "very-high"

    restored = Project.from_dict(data)
    assert restored.output_resolution == "720p"
    assert restored.output_quality == "very-high"


def test_output_options_are_undoable():
    session = ProjectSession(Project())
    session.set_output_resolution("720p")
    session.set_output_quality("very-high")

    assert session.project.output_resolution == "720p"
    assert session.project.output_quality == "very-high"

    session.undo()
    assert session.project.output_quality == "high"
    session.undo()
    assert session.project.output_resolution == "1080p"
