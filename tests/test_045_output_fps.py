from panopilot.output_profile import (
    AUTO_OUTPUT_FPS,
    DEFAULT_OUTPUT_FPS,
    OUTPUT_FPS_SELECTIONS,
    output_fps_label,
    output_profile_for_aspect,
    output_profile_for_project,
    resolve_output_fps,
)
from panopilot.project import Project
from panopilot.session import ProjectSession


def test_new_projects_default_to_auto_60fps_device_friendly_delivery():
    project = Project()
    profile = output_profile_for_project(project)

    assert project.output_fps == "auto"
    assert DEFAULT_OUTPUT_FPS == "auto"
    assert AUTO_OUTPUT_FPS == 60.0
    assert profile.fps == 60.0
    assert profile.fps_selection == "auto"
    assert profile.fps_auto_selected is True


def test_auto_never_upsamples_future_slower_source_profiles():
    assert resolve_output_fps("auto", source_fps=100.0) == 60.0
    assert resolve_output_fps("auto", source_fps=60.0) == 60.0
    assert resolve_output_fps("auto", source_fps=50.0) == 50.0
    assert resolve_output_fps("auto", source_fps=30.0) == 30.0
    assert resolve_output_fps("auto", source_fps=25.0) == 25.0


def test_user_can_select_all_supported_delivery_rates():
    assert OUTPUT_FPS_SELECTIONS == (
        "auto",
        "24",
        "25",
        "30",
        "50",
        "60",
    )

    for selection in OUTPUT_FPS_SELECTIONS[1:]:
        profile = output_profile_for_aspect(
            "16:9",
            "1080p",
            selection,
        )
        assert profile.fps == float(selection)
        assert profile.fps_auto_selected is False


def test_schema_v8_migrates_to_30fps_to_preserve_iteration1_export_behavior():
    project = Project.from_dict(
        {
            "schema_version": 8,
            "output_frame": {
                "aspect": "16:9",
                "resolution": "1080p",
                "quality": "high",
            },
            "clips": [],
        }
    )

    assert project.schema_version == 10
    assert project.output_fps == "30"
    assert output_profile_for_project(project).fps == 30.0


def test_schema_v9_persists_auto_or_explicit_fps():
    project = Project(output_fps="50")
    data = project.to_dict()

    assert data["schema_version"] == 10
    assert data["output_frame"]["fps"] == "50"

    restored = Project.from_dict(data)
    assert restored.output_fps == "50"
    assert output_profile_for_project(restored).fps == 50.0


def test_fps_selection_is_undoable():
    session = ProjectSession(Project())

    session.set_output_fps("30")
    assert session.project.output_fps == "30"

    session.undo()
    assert session.project.output_fps == "auto"

    session.redo()
    assert session.project.output_fps == "30"


def test_auto_label_explains_effective_default():
    assert output_fps_label("auto") == "Auto (60 fps recommended)"
