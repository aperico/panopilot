import json

from panopilot.recovery import (
    parse_candidate_indexes,
    rebuild_project_from_cache,
)
from panopilot.project import load_project


def _write_cache(
    root,
    key,
    source,
    duration,
):
    entry = (
        root
        / key
    )
    entry.mkdir(
        parents=True,
    )
    stat = source.stat()

    (
        entry
        / "metadata.json"
    ).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cache_key": key,
                "source_identity": {
                    "path": str(
                        source.resolve()
                    ),
                    "size": stat.st_size,
                    "mtime_ns": (
                        stat.st_mtime_ns
                    ),
                },
                "source_duration": (
                    duration
                ),
                "profile": {},
            }
        ),
        encoding="utf-8",
    )


def test_parse_indexes_preserves_user_clip_order():
    assert parse_candidate_indexes(
        "2, 1",
        candidate_count=3,
    ) == [
        2,
        1,
    ]


def test_rebuild_project_from_cache_uses_selected_order(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "XDG_DATA_HOME",
        str(
            tmp_path
            / "xdg-data"
        ),
    )

    source_a = (
        tmp_path
        / "a.OSV"
    )
    source_b = (
        tmp_path
        / "b.OSV"
    )
    source_a.write_bytes(
        b"a"
    )
    source_b.write_bytes(
        b"b"
    )

    cache_root = (
        tmp_path
        / "cache"
    )
    _write_cache(
        cache_root,
        "a",
        source_a,
        6.0,
    )
    _write_cache(
        cache_root,
        "b",
        source_b,
        17.7,
    )

    project_path = (
        tmp_path
        / "project.json"
    )

    # Discovery sorting is source-name alphabetical => 1=a, 2=b.
    result = rebuild_project_from_cache(
        project_path,
        indexes=[
            2,
            1,
        ],
        cache_dir=cache_root,
        output_aspect="16:9",
        camera_motion_easing=(
            "ease-in-out"
        ),
        camera_motion_strength=0.7,
    )

    assert result["clip_count"] == 2

    project = load_project(
        project_path
    )

    assert project.clips[0].id == "clip-1"
    assert project.clips[0].source == str(
        source_b.resolve()
    )
    assert project.clips[1].source == str(
        source_a.resolve()
    )
    assert (
        project.camera_motion_easing
        == "ease-in-out"
    )
    assert (
        project.camera_motion_strength
        == 0.7
    )
