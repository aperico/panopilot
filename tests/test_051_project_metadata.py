from panopilot.project import Project, SCHEMA_VERSION
from panopilot.session import ProjectSession


def test_project_name_roundtrips_in_schema_10():
    project = Project(name="Summer 360")
    data = project.to_dict()
    assert SCHEMA_VERSION == 10
    assert data["name"] == "Summer 360"
    restored = Project.from_dict(data)
    assert restored.name == "Summer 360"


def test_legacy_project_gets_safe_default_name():
    restored = Project.from_dict({"schema_version": 9, "clips": []})
    assert restored.name == "Untitled Project"


def test_project_name_edit_is_transactional():
    session = ProjectSession(Project())
    result = session.set_project_name("My Ride")
    assert result["changed"]
    assert session.project.name == "My Ride"
    session.undo()
    assert session.project.name == "Untitled Project"
