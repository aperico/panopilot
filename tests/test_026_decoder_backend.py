import pytest

import panopilot.project_export as export_module
from panopilot.project_export import (
    _decoder_hwaccel_args,
    _lens_decoder_command,
    _select_decoder_backend,
)


def test_software_decoder_has_no_hwaccel_args():
    assert _decoder_hwaccel_args(
        "software"
    ) == []


def test_vaapi_decoder_args_require_device():
    assert _decoder_hwaccel_args(
        "vaapi",
        "/dev/dri/renderD128",
    ) == [
        "-hwaccel",
        "vaapi",
        "-hwaccel_device",
        "/dev/dri/renderD128",
    ]

    with pytest.raises(
        ValueError
    ):
        _decoder_hwaccel_args(
            "vaapi"
        )


def test_lens_decoder_places_vaapi_options_before_input():
    command = _lens_decoder_command(
        "source.OSV",
        0,
        1,
        1920,
        1920,
        fps=30.0,
        start=0.0,
        frame_count=1,
        decoder_backend="vaapi",
        vaapi_device="/dev/dri/renderD128",
    )

    assert (
        command.index(
            "-hwaccel"
        )
        < command.index(
            "-i"
        )
    )


def test_auto_selects_vaapi_only_after_exact_smoke_test(
    monkeypatch,
):
    monkeypatch.setattr(
        export_module,
        "_candidate_vaapi_devices",
        lambda preferred=None: [
            "/dev/dri/renderD128"
        ],
    )
    monkeypatch.setattr(
        export_module,
        "_smoke_test_lens_decoder",
        lambda *args, **kwargs: (
            True,
            "passed",
        ),
    )

    selection = _select_decoder_backend(
        "source.OSV",
        0,
        1,
        1920,
        1920,
        fps=30.0,
        start=0.0,
        requested="auto",
    )

    assert selection.backend == "vaapi"
    assert selection.smoke_tested is True
    assert selection.fallback is False


def test_auto_falls_back_when_vaapi_smoke_fails(
    monkeypatch,
):
    monkeypatch.setattr(
        export_module,
        "_candidate_vaapi_devices",
        lambda preferred=None: [
            "/dev/dri/renderD128"
        ],
    )
    monkeypatch.setattr(
        export_module,
        "_smoke_test_lens_decoder",
        lambda *args, **kwargs: (
            False,
            "device failed",
        ),
    )

    selection = _select_decoder_backend(
        "source.OSV",
        0,
        1,
        1920,
        1920,
        fps=30.0,
        start=0.0,
        requested="auto",
    )

    assert selection.backend == "software"
    assert selection.fallback is True
    assert "device failed" in selection.reason


def test_explicit_vaapi_fails_when_smoke_fails(
    monkeypatch,
):
    monkeypatch.setattr(
        export_module,
        "_candidate_vaapi_devices",
        lambda preferred=None: [
            "/dev/dri/renderD128"
        ],
    )
    monkeypatch.setattr(
        export_module,
        "_smoke_test_lens_decoder",
        lambda *args, **kwargs: (
            False,
            "device failed",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="runtime lens-decode smoke test failed",
    ):
        _select_decoder_backend(
            "source.OSV",
            0,
            1,
            1920,
            1920,
            fps=30.0,
            start=0.0,
            requested="vaapi",
        )


def test_software_mode_does_not_probe_vaapi(
    monkeypatch,
):
    monkeypatch.setattr(
        export_module,
        "_smoke_test_lens_decoder",
        lambda *args, **kwargs: pytest.fail(
            "software mode must not smoke-test VAAPI"
        ),
    )

    selection = _select_decoder_backend(
        "source.OSV",
        0,
        1,
        1920,
        1920,
        fps=30.0,
        start=0.0,
        requested="software",
    )

    assert selection.backend == "software"
    assert selection.smoke_tested is False
