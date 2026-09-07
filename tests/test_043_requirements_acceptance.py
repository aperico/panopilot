from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[
    1
]


def test_quantitative_register_has_no_remaining_tbd_values():
    text = (
        ROOT
        / "docs"
        / "03_system_requirements.md"
    ).read_text(
        encoding="utf-8"
    )

    assert "**Status:** TBD" not in text

    for token in (
        "dji-osmo360-dual-1920-hevc-100fps-v1",
        "0.05 source-panorama",
        "100 ms",
        "250 ms",
        "Preview audio/video synchronization error shall not exceed **100 ms**",
    ):
        assert token in text


def test_quantitative_field_gates_are_closed_after_reference_run():
    text = (
        ROOT
        / "docs"
        / "06_requirements_traceability.md"
    ).read_text(
        encoding="utf-8"
    )

    partial_rows = [
        line
        for line in text.splitlines()
        if line.startswith(
            "| SYS-"
        )
        and "| PARTIAL |"
        in line
    ]

    assert partial_rows == []

    for requirement_id in (
        "SYS-AUDIO-003",
        "SYS-PERF-001",
        "SYS-PERF-002",
        "SYS-MEDIA-001",
        "SYS-CAM-009",
    ):
        assert any(
            line.startswith(
                f"| {requirement_id} |"
            )
            and "| PASS |"
            in line
            for line in text.splitlines()
        )


def test_quantitative_acceptance_document_is_part_of_baseline():
    text = (
        ROOT
        / "docs"
        / "07_quantitative_acceptance.md"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "panopilot acceptance-run"
        in text
    )
    assert (
        "acceptance-043.json"
        in text
    )
    assert (
        "Fedora / AMD Radeon 890M"
        in text
    )
