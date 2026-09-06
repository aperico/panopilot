from panopilot.source import lens_streams


def test_lens_stream_selection_ignores_attached_picture():
    probe = {
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "width": 1920,
                "height": 1920,
                "disposition": {"attached_pic": 0},
            },
            {
                "index": 1,
                "codec_type": "video",
                "width": 1920,
                "height": 1920,
                "disposition": {"attached_pic": 0},
            },
            {
                "index": 7,
                "codec_type": "video",
                "width": 688,
                "height": 344,
                "disposition": {"attached_pic": 1},
            },
        ]
    }

    streams = lens_streams(probe)
    assert [s["index"] for s in streams] == [0, 1]
