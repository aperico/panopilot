import json
from pathlib import Path

from panopilot.cache import (
    discover_cached_sources,
)


def _metadata(
    cache_root,
    key,
    source,
    duration,
):
    entry = (
        cache_root
        / key
    )
    entry.mkdir(
        parents=True,
    )
    path = (
        entry
        / "metadata.json"
    )
    source = Path(
        source
    )
    stat = source.stat()

    path.write_text(
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


def test_discover_cached_sources_deduplicates_source_paths(
    tmp_path,
):
    source = (
        tmp_path
        / "a.OSV"
    )
    source.write_bytes(
        b"data"
    )
    cache = (
        tmp_path
        / "cache"
    )

    _metadata(
        cache,
        "old",
        source,
        6.0,
    )
    _metadata(
        cache,
        "new",
        source,
        6.0,
    )

    candidates = discover_cached_sources(
        cache_dir=cache,
        existing_only=True,
    )

    assert len(
        candidates
    ) == 1
    assert candidates[0].source == (
        source.resolve()
    )
    assert candidates[0].source_duration == 6.0


def test_discover_cached_sources_can_include_missing_source(
    tmp_path,
):
    cache = (
        tmp_path
        / "cache"
    )
    entry = (
        cache
        / "x"
    )
    entry.mkdir(
        parents=True,
    )
    missing = (
        tmp_path
        / "missing.OSV"
    )
    (
        entry
        / "metadata.json"
    ).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cache_key": "x",
                "source_identity": {
                    "path": str(
                        missing
                    ),
                    "size": 10,
                    "mtime_ns": 20,
                },
                "source_duration": 17.7,
                "profile": {},
            }
        ),
        encoding="utf-8",
    )

    all_items = discover_cached_sources(
        cache_dir=cache,
        existing_only=False,
    )
    existing = discover_cached_sources(
        cache_dir=cache,
        existing_only=True,
    )

    assert len(all_items) == 1
    assert all_items[0].exists is False
    assert existing == []
