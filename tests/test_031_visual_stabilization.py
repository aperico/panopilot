import numpy as np
from panopilot.visual_stabilization import _correction_fits_crop,_fill_invalid,_gaussian_smooth,_max_feasible_alpha

def test_fill_invalid_interpolates_missing_motion():
    values=np.array([0.0,np.nan,2.0]); valid=np.array([True,False,True])
    assert np.allclose(_fill_invalid(values,valid),[0.0,1.0,2.0])

def test_gaussian_smoothing_reduces_impulse():
    values=np.zeros(21); values[10]=10.0; out=_gaussian_smooth(values,3.0)
    assert 0.0 < out[10] < 10.0
    assert np.isclose(out.sum(),10.0,atol=1e-6)

def test_identity_fits_crop():
    assert _correction_fits_crop(1920,1080,25.0,0.0,0.0,0.0,1.0)

def test_large_translation_is_crop_clamped():
    alpha=_max_feasible_alpha(1920,1080,25.0,500.0,0.0,0.0)
    assert 0.0 < alpha < 1.0
    assert _correction_fits_crop(1920,1080,25.0,500.0,0.0,0.0,alpha)
