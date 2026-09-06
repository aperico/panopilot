from pathlib import Path

from panopilot.cache import (
    PreviewProfile,
    frame_index_for_time,
    preview_cache_key,
    preview_cache_is_valid,
    source_identity,
)


def test_preview_cache_key_changes_when_source_changes(tmp_path):
    source = tmp_path / "sample.OSV"
    source.write_bytes(b"one")
    profile = PreviewProfile()
    first = preview_cache_key(source, profile)
    source.write_bytes(b"two-two")
    second = preview_cache_key(source, profile)
    assert first != second


def test_preview_cache_key_changes_with_profile(tmp_path):
    source = tmp_path / "sample.OSV"
    source.write_bytes(b"x")
    a = preview_cache_key(source, PreviewProfile(fps=20.0))
    b = preview_cache_key(source, PreviewProfile(fps=15.0))
    assert a != b


def test_cache_validity_requires_matching_identity_and_profile(tmp_path):
    source = tmp_path / "sample.OSV"
    source.write_bytes(b"source")
    video = tmp_path / "panorama.mp4"
    video.write_bytes(b"video")
    meta = tmp_path / "metadata.json"
    profile = PreviewProfile()

    import json
    meta.write_text(json.dumps({
        "schema_version": 1,
        "source_identity": source_identity(source),
        "profile": profile.to_dict(),
    }))

    assert preview_cache_is_valid(source, profile, video, meta)
    assert not preview_cache_is_valid(
        source,
        PreviewProfile(fps=10.0),
        video,
        meta,
    )


def test_frame_index_for_time_clamps_and_rounds():
    assert frame_index_for_time(0.0, 20.0, 100) == 0
    assert frame_index_for_time(1.02, 20.0, 100) == 20
    assert frame_index_for_time(100.0, 20.0, 100) == 99
