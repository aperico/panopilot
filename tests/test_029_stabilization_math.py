import math
import numpy as np
from panopilot.attitude import (
    smooth_quaternions_centered, stabilization_correction,
    stabilized_horizon_rotation,
)

def qz(deg):
    h=math.radians(deg)/2.0
    return np.array([math.cos(h),0.0,0.0,math.sin(h)],dtype=np.float64)

def test_quaternion_smoothing_handles_sign_equivalence():
    q=qz(15); seq=np.array([q,-q,q,-q,q])
    sm=smooth_quaternions_centered(seq,1.0)
    assert np.all(np.abs(sm @ q) > 0.999999)

def test_zero_stabilization_is_identity():
    assert np.allclose(stabilization_correction(qz(10),qz(0),0.0),np.eye(3))

def test_full_stabilization_is_rotation():
    r=stabilization_correction(qz(10),qz(0),1.0)
    assert not np.allclose(r,np.eye(3))
    assert np.allclose(r.T@r,np.eye(3),atol=1e-10)

def test_amount_zero_preserves_horizon_leveling():
    g=np.array([0.05,-0.998,0.02]); g/=np.linalg.norm(g)
    r,d=stabilized_horizon_rotation(
        raw_quaternion=qz(8), smoothed_quaternion=qz(8), leveled_gravity=g,
        stabilization_amount=0.0, level_horizon=True, level_strength=1.0)
    assert np.allclose(r@g,np.array([0.,-1.,0.]),atol=1e-8)
    assert d['stabilization_amount']==0.0
