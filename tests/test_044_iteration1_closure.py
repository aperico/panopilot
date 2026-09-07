import json
from pathlib import Path

from panopilot.cli import build_parser


ROOT = Path(
    __file__
).resolve().parents[
    1
]


def test_rtm_is_exactly_208_pass_with_no_partial_or_open():
    text = (
        ROOT
        / "docs"
        / "06_requirements_traceability.md"
    ).read_text(
        encoding="utf-8"
    )

    rows = [
        line
        for line in text.splitlines()
        if line.startswith(
            "| SYS-"
        )
    ]

    assert len(
        rows
    ) == 208
    assert all(
        "| PASS |"
        in row
        for row in rows
    )
    assert not any(
        "| PARTIAL |"
        in row
        for row in rows
    )
    assert not any(
        "| OPEN |"
        in row
        for row in rows
    )
    assert (
        "208 PASS / 0 PARTIAL / 0 OPEN"
        in text
    )


def test_distributed_certificate_is_sanitized_and_pass():
    path = (
        ROOT
        / "docs"
        / "iteration1_acceptance_certificate.json"
    )
    certificate = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert certificate[
        "status"
    ] == "PASS"
    assert certificate[
        "requirements_pass"
    ] == 208

    serialized = path.read_text(
        encoding="utf-8"
    ).lower()

    for forbidden in (
        "/home/",
        '"fingerprint":',
        '"resolved_path":',
        "/panorama.mp4",
    ):
        assert forbidden not in serialized


def test_acceptance_certify_cli_is_available():
    args = build_parser().parse_args(
        [
            "acceptance-certify",
            "acceptance.json",
        ]
    )

    assert (
        args.report
        == "acceptance.json"
    )
    assert (
        args.output
        == "results/iteration1-acceptance-certificate.json"
    )


def test_formal_verification_report_closes_iteration1():
    text = (
        ROOT
        / "docs"
        / "08_iteration1_verification_report.md"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "PASS — ITERATION 1 CLOSED"
        in text
    )
    assert (
        "208 normative Iteration-1 requirements are PASS"
        in text
    )
