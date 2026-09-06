from panopilot.project import Project
from panopilot.project_editor import (
    clip_list_rows,
    import_sources_into_session,
)
from panopilot.session import ProjectSession


def test_multi_select_import_preserves_order():
    session = ProjectSession(
        Project()
    )

    result = import_sources_into_session(
        session,
        [
            "a.OSV",
            "b.OSV",
            "c.OSV",
        ],
    )

    assert len(
        result["added_clip_ids"]
    ) == 3

    assert [
        clip.source
        for clip in session.project.clips
    ] == [
        "a.OSV",
        "b.OSV",
        "c.OSV",
    ]


def test_multi_select_import_skips_existing_source():
    session = ProjectSession(
        Project()
    )

    import_sources_into_session(
        session,
        ["a.OSV"],
    )

    result = import_sources_into_session(
        session,
        [
            "a.OSV",
            "b.OSV",
        ],
    )

    assert [
        clip.source
        for clip in session.project.clips
    ] == [
        "a.OSV",
        "b.OSV",
    ]

    assert result["skipped"] == [
        {
            "source": "a.OSV",
            "reason": "already-in-project",
        }
    ]


def test_clip_rows_follow_project_order():
    session = ProjectSession(
        Project()
    )

    import_sources_into_session(
        session,
        [
            "a.OSV",
            "b.OSV",
        ],
    )

    rows = clip_list_rows(
        session.project,
        {
            "clip-1": 6.0,
            "clip-2": 8.0,
        },
    )

    assert [
        row["number"]
        for row in rows
    ] == [
        1,
        2,
    ]

    assert [
        row["source"]
        for row in rows
    ] == [
        "a.OSV",
        "b.OSV",
    ]
