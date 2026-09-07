from panopilot.cache import PreviewProfile

def test_stabilization_is_in_preview_profile():
    a=PreviewProfile(stabilization_amount=0.2).to_dict()
    b=PreviewProfile(stabilization_amount=0.8).to_dict()
    assert a['stabilization_amount'] != b['stabilization_amount']
    assert b['stabilization_smoothing_ms']==400.0


def test_cache_records_adaptive_algorithm_version():
    assert PreviewProfile().to_dict()["stabilization_algorithm"] == "adaptive-highrate-v1"
