from panopilot.preview import _decoder_command, _encoder_command


def test_decoder_uses_one_filter_graph_for_both_lenses():
    cmd = _decoder_command(
        "sample.OSV",
        0,
        1,
        1920,
        1920,
        30.0,
        1.0,
        3.0,
    )

    graph = cmd[cmd.index("-filter_complex") + 1]

    assert "[0:0]" in graph
    assert "[0:1]" in graph
    assert "hstack=inputs=2" in graph


def test_encoder_can_include_source_audio():
    cmd = _encoder_command(
        "sample.OSV",
        "preview.mp4",
        1920,
        960,
        30.0,
        1.0,
        3.0,
        20,
        "veryfast",
        True,
    )

    assert "-map" in cmd
    assert "1:a:0?" in cmd
    assert "aac" in cmd
