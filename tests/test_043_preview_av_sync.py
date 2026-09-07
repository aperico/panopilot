from pathlib import Path

import panopilot.project_player as player_module


def test_project_preview_uses_audio_position_as_playback_clock():
    source = Path(
        player_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "self.media_player.position()"
        in source
    )
    assert (
        "span_by_clip_id"
        in source
    )
    assert (
        "audio_source_time"
        in source
    )
    assert (
        "PreciseTimer"
        in source
    )
