from panopilot.clip_strip import build_clip_strip_entries


def test_clip_strip_entries_are_compact_and_framework_agnostic():
    rows = [{
        "number": 2,
        "clip_id": "clip-2",
        "source": "/media/family.OSV",
        "source_name": "family.OSV",
        "trim_in": 1.25,
        "trim_out": 7.5,
        "duration": 6.25,
        "camera_position_count": 3,
        "source_status": {"status": "ok", "message": "Source verified"},
    }]

    entries = build_clip_strip_entries(rows, {"clip-2": "succeeded"})

    assert len(entries) == 1
    entry = entries[0]
    assert entry.clip_id == "clip-2"
    assert entry.title == "Clip 02"
    assert entry.subtitle == "File 6.2s  ·  3 Camera Positions  ·  Ready"
    assert "family.OSV" in entry.tooltip
    assert "/media/family.OSV" in entry.tooltip
    assert "Trim: 1.250s → 7.500s" in entry.tooltip
    assert entry.preview_status == "succeeded"


def test_clip_strip_does_not_require_qt_for_presentation_mapping():
    # The CLI imports project_editor in headless environments.  The compact
    # presentation mapping therefore stays importable without PySide6.
    entries = build_clip_strip_entries([], {})
    assert entries == []
